"""Integration and unit tests for RippleMap Investigation Agent and Incident Memory (Milestone 5).

Validates:
- Scenario A: SUB-001 end-to-end cascade, memory retrieval, RippleScore, and recovery optimizer coordination.
- Scenario B: Repeated read-only agent executions create zero duplicate records and zero mutations.
- Scenario C: Explicit memory write persistence with verified idempotency across repeat calls.
- Scenario D: Historical incident memory retrieval with explicit grounded relevance reasons.
- Scenario E: Outcome distinction (observed historical outcome vs proposed vs simulated vs missing).
- Scenario F: Unknown source and unsupported questions handled safely without evidence fabrication.
- Scenario G: Explainable top-ranked recovery plan justification grounded in scoring math and trade-offs.
- Scenario H: Graph integrity — zero mutation of infrastructure node operational statuses.
- Grounded Q&A: Full coverage of all 6 evidence-grounded questions.
"""

import pytest
from app.db import db_client
from app.schema import (
    OutcomeType,
    ImpactClassification,
    AgentBriefing,
    GroundedAnswer,
)
from app.incident_memory import (
    classify_action_outcome,
    query_incident_memory,
    record_investigation_memory,
)
from app.investigation_agent import (
    run_investigation_agent,
    answer_grounded_question,
)
from app.impact_engine import investigate_incident
from app.ripple_score import compute_incident_ripple_scores
from app.recovery_optimizer import optimize_recovery_plans


@pytest.fixture(scope="module")
def db():
    return db_client


# =============================================================================
# SCENARIO A: End-to-End SUB-001 Cascade, Memory, Scoring, and Optimization
# =============================================================================

def test_scenario_a_sub001_end_to_end_briefing(db):
    """Scenario A: Agent investigates SUB-001 cascade, retrieves incident memory,
    ranks exposed services via RippleScore, compares recovery plans, and produces
    a structured AgentBriefing.
    """
    briefing = run_investigation_agent("SUB-001", persist_memory=False, client=db)

    assert isinstance(briefing, AgentBriefing)
    assert briefing.source_node_id == "SUB-001"
    assert briefing.source_node_name == "Metro Central Substation"
    assert briefing.source_status == "OPERATIONAL"
    assert briefing.is_persisted_memory is False

    # Cascading Findings
    total_findings = len(briefing.direct_findings) + len(briefing.downstream_findings)
    assert total_findings == 8
    assert len(briefing.direct_findings) == 6
    assert len(briefing.downstream_findings) == 2

    direct_ids = {f.asset_id for f in briefing.direct_findings}
    assert direct_ids == {"EMERG-001", "PUMP-001", "ROAD-001", "TOWER-001", "CLINIC-001", "PUMP-002"}

    downstream_ids = {f.asset_id for f in briefing.downstream_findings}
    assert downstream_ids == {"HOSP-001", "HOSP-002"}

    all_affected_ids = direct_ids | downstream_ids
    assert "HOSP-002" in all_affected_ids
    assert "ROAD-002" not in all_affected_ids  # ROAD-002 is an alternate bypass route, not an affected asset!

    # Verify Generator Mappings from Graph
    hosp1 = next(f for f in briefing.downstream_findings if f.asset_id == "HOSP-001")
    assert hosp1.backup_available is True
    assert hosp1.backup_details[0]["generator_id"] == "GEN-001"

    hosp2 = next(f for f in briefing.downstream_findings if f.asset_id == "HOSP-002")
    assert hosp2.backup_available is True
    assert hosp2.backup_details[0]["generator_id"] == "GEN-003"

    emerg1 = next(f for f in briefing.direct_findings if f.asset_id == "EMERG-001")
    assert emerg1.backup_available is False
    assert emerg1.backup_details == []

    pump1 = next(f for f in briefing.direct_findings if f.asset_id == "PUMP-001")
    assert pump1.backup_available is True
    assert pump1.backup_details[0]["generator_id"] == "GEN-002"
    assert pump1.backup_details[0]["is_insufficient"] is True

    # Memory Retrieval (seeded baseline INC-2026-001)
    assert len(briefing.historical_incidents) >= 1
    inc_ids = [m.incident_id for m in briefing.historical_incidents]
    assert "INC-2026-001" in inc_ids

    # Transparent Canonical RippleScores
    assert len(briefing.ripple_scores) == 9  # SUB-001 + 8 affected assets
    expected_scores = [85.0, 60.0, 57.0, 50.0, 50.0, 25.0, 7.0, 5.0, 2.0]
    expected_ids = ["SUB-001", "ROAD-001", "PUMP-001", "EMERG-001", "TOWER-001", "HOSP-001", "CLINIC-001", "HOSP-002", "PUMP-002"]
    assert [s.total_score for s in briefing.ripple_scores] == expected_scores
    assert [s.asset_id for s in briefing.ripple_scores] == expected_ids

    # Recovery Plans
    assert len(briefing.evaluated_plans) >= 2
    assert briefing.recommended_plan is not None
    assert briefing.recommended_plan.composite_benefit_score > 0
    assert len(briefing.recommended_next_steps) >= 3

    # Grounded Q&A included
    assert len(briefing.grounded_answers) >= 2
    for ans in briefing.grounded_answers:
        assert isinstance(ans, GroundedAnswer)
        assert ans.evidence_sufficient is True


# =============================================================================
# SCENARIO B: Repeated Read-Only Executions Preserve Zero Mutation
# =============================================================================

def test_scenario_b_repeated_read_only_agent_zero_mutation(db):
    """Scenario B: Running read-only investigations repeatedly must NEVER create
    new memory records, relationships, or mutate operational statuses.
    """
    initial_nodes = db.query("MATCH (n) RETURN count(n)")[0][0]
    initial_rels = db.query("MATCH ()-[r]->() RETURN count(r)")[0][0]

    # Run agent twice in read-only mode
    briefing1 = run_investigation_agent("SUB-001", question="What could be affected if SUB-001 fails?", persist_memory=False, client=db)
    briefing2 = run_investigation_agent("SUB-001", question="Which critical services have no viable alternate supply?", persist_memory=False, client=db)

    assert briefing1.is_persisted_memory is False
    assert briefing2.is_persisted_memory is False

    final_nodes = db.query("MATCH (n) RETURN count(n)")[0][0]
    final_rels = db.query("MATCH ()-[r]->() RETURN count(r)")[0][0]

    assert final_nodes == initial_nodes, "Read-only agent execution mutated node count!"
    assert final_rels == initial_rels, "Read-only agent execution mutated relationship count!"


# =============================================================================
# SCENARIO C: Explicit Memory Write & Idempotency
# =============================================================================

def test_scenario_c_explicit_memory_write_and_idempotency(db):
    """Scenario C: Memory is written ONLY when explicitly requested (persist_memory=True).
    Repeating the explicit persistence must update rather than duplicate graph records.
    """
    test_inc_id = "INC-TEST-IDEMPOTENT-001"

    # Clean up test node if previously present
    db.query("""
    MATCH (inc:Incident {id: $inc_id})
    OPTIONAL MATCH (inc)-[:USED_ACTION]->(act:RecoveryAction)
    OPTIONAL MATCH (inc)-[:SUPPORTED_BY]->(evd:EvidenceRecord)
    DETACH DELETE inc, act, evd
    """, {"inc_id": test_inc_id})

    nodes_before = db.query("MATCH (n) RETURN count(n)")[0][0]

    # 1. First explicit write
    briefing_write_1 = run_investigation_agent(
        "SUB-001",
        persist_memory=True,
        incident_id=test_inc_id,
        client=db,
    )
    assert briefing_write_1.is_persisted_memory is True
    assert briefing_write_1.memory_persistence_details is not None
    assert briefing_write_1.memory_persistence_details["incident_id"] == test_inc_id

    nodes_after_first_write = db.query("MATCH (n) RETURN count(n)")[0][0]
    rels_after_first_write = db.query("MATCH ()-[r]->() RETURN count(r)")[0][0]

    # Deep Relationship and Provenance Inspection after Write 1
    rels_type_rows_1 = db.query(f"MATCH (inc:Incident {{id: '{test_inc_id}'}})-[r]->() RETURN type(r), count(r)")
    rels_by_type_1 = dict(rels_type_rows_1)
    assert rels_by_type_1["TRIGGERED_BY"] == 1
    assert rels_by_type_1["AFFECTED"] == 8
    assert rels_by_type_1["SUPPORTED_BY"] == 8
    assert rels_by_type_1["USED_ACTION"] == 1

    act_target_count_1 = db.query(f"MATCH (inc:Incident {{id: '{test_inc_id}'}})-[:USED_ACTION]->(act)-[r:TARGETS]->() RETURN count(r)")[0][0]
    assert act_target_count_1 == 1

    # Verify Provenance Properties
    prov_row = db.query(f"MATCH (inc:Incident {{id: '{test_inc_id}'}}) RETURN inc.title, inc.failure_source, inc.simulated, inc.resolved, inc.notes")[0]
    assert "SUB-001" in prov_row[0]
    assert prov_row[1] == "SUB-001"
    assert prov_row[2] is True   # simulated
    assert prov_row[3] is False  # resolved (unconfirmed)
    assert "Deterministic agent investigation" in prov_row[4]

    # Verify Action Status is PROPOSED (Never Confirmed!)
    act_status = db.query(f"MATCH (inc:Incident {{id: '{test_inc_id}'}})-[:USED_ACTION]->(act) RETURN act.status")[0][0]
    assert act_status == "PROPOSED"

    # 2. Second explicit write with SAME incident_id (Idempotency test)
    briefing_write_2 = run_investigation_agent(
        "SUB-001",
        persist_memory=True,
        incident_id=test_inc_id,
        client=db,
    )
    assert briefing_write_2.is_persisted_memory is True

    nodes_after_second_write = db.query("MATCH (n) RETURN count(n)")[0][0]
    rels_after_second_write = db.query("MATCH ()-[r]->() RETURN count(r)")[0][0]

    # Assert exact idempotency: NO duplicate nodes or edges created
    assert nodes_after_second_write == nodes_after_first_write, "Duplicate nodes created on repeat memory write!"
    assert rels_after_second_write == rels_after_first_write, "Duplicate relationships created on repeat memory write!"

    # Deep Relationship Inspection after Write 2
    rels_type_rows_2 = db.query(f"MATCH (inc:Incident {{id: '{test_inc_id}'}})-[r]->() RETURN type(r), count(r)")
    rels_by_type_2 = dict(rels_type_rows_2)
    assert rels_by_type_2 == rels_by_type_1, "Relationship counts by type mutated on repeat memory write!"

    # Clean up test incident to leave graph in pristine state
    db.query(f"""
    MATCH (inc:Incident {{id: '{test_inc_id}'}})
    OPTIONAL MATCH (inc)-[:USED_ACTION]->(act:RecoveryAction)
    OPTIONAL MATCH (inc)-[:SUPPORTED_BY]->(evd:EvidenceRecord)
    DETACH DELETE inc, act, evd
    """)

    nodes_after_cleanup = db.query("MATCH (n) RETURN count(n)")[0][0]
    assert nodes_after_cleanup == nodes_before


# =============================================================================
# SCENARIO D: Historical Relevance Matching
# =============================================================================

def test_scenario_d_historical_memory_relevance_reasons(db):
    """Scenario D: Historical incident memory returns explicit relevance reasons
    grounded in matching root causes, overlapping assets, or shared evidence paths.
    """
    matches = query_incident_memory("SUB-001", affected_asset_ids=["HOSP-001", "TOWER-001"], client=db)
    assert len(matches) >= 1

    baseline_match = next((m for m in matches if m.incident_id == "INC-2026-001"), None)
    assert baseline_match is not None

    # Verify explicit relevance reasons
    reason = baseline_match.relevance_reason
    assert "Direct root cause match" in reason or "Overlapping affected service" in reason
    assert "SUB-001" in reason or "HOSP-001" in reason or "TOWER-001" in reason

    # Verify matching assets contains HOSP-001 or TOWER-001
    assert "HOSP-001" in baseline_match.matching_assets or "TOWER-001" in baseline_match.matching_assets

    # Verify action and evidence record linkage
    assert baseline_match.recovery_action_id == "ACT-2026-001"
    assert baseline_match.recovery_action_name == "Auxiliary Grid Re-route from SUB-002"
    assert baseline_match.evidence_path_summary is not None
    assert "SUB-001" in baseline_match.evidence_path_summary


# =============================================================================
# SCENARIO E: Outcome Distinction (Observed vs Simulated vs Proposed)
# =============================================================================

def test_scenario_e_outcome_classification_rigor():
    """Scenario E: Confirms that proposed or simulated actions are NEVER presented
    as confirmed successful recoveries, and missing outcome data is classified accurately.
    """
    # 1. Observed successful outcome
    type1, desc1 = classify_action_outcome("EXECUTED_SUCCESSFUL")
    assert type1 == OutcomeType.CONFIRMED_SUCCESSFUL
    assert "confirmed executed with verified operational recovery" in desc1

    # 2. Observed failed outcome
    type2, desc2 = classify_action_outcome("EXECUTED_FAILED")
    assert type2 == OutcomeType.CONFIRMED_FAILED
    assert "failed to achieve operational recovery" in desc2

    # 3. Action taken, outcome verification pending
    type3, desc3 = classify_action_outcome("EXECUTED_PARTIAL")
    assert type3 == OutcomeType.RECORDED_ACTION_TAKEN

    # 4. In-memory simulated outcome (NOT real-world confirmed!)
    type4, desc4 = classify_action_outcome("SIMULATED")
    assert type4 == OutcomeType.SIMULATED_OUTCOME
    assert "not a confirmed real-world recovery" in desc4

    # 5. Proposed/recommended action (NOT real-world confirmed!)
    type5, desc5 = classify_action_outcome("PROPOSED")
    assert type5 == OutcomeType.PROPOSED_ACTION
    assert "no confirmed field execution" in desc5

    type5b, desc5b = classify_action_outcome("RECOMMENDED")
    assert type5b == OutcomeType.PROPOSED_ACTION

    # 6. Missing outcome data
    type6, desc6 = classify_action_outcome(None)
    assert type6 == OutcomeType.MISSING_OUTCOME_DATA
    assert "unrecorded" in desc6


# =============================================================================
# SCENARIO F: Unknown Source and Unsupported Question
# =============================================================================

def test_scenario_f_unknown_source_graceful_handling(db):
    """Scenario F1: Unknown source node ID returns structured briefing without crashing
    and without fabricating evidence.
    """
    briefing = run_investigation_agent("NON_EXISTENT_SOURCE_999", persist_memory=False, client=db)

    assert isinstance(briefing, AgentBriefing)
    assert briefing.source_status == "UNKNOWN"
    assert briefing.direct_findings == []
    assert briefing.downstream_findings == []
    assert briefing.ripple_scores == []
    assert briefing.evaluated_plans == []
    assert briefing.confidence_assessment["overall_confidence"] == 0.0

    # Grounded answer explains absence of source
    assert len(briefing.grounded_answers) == 1
    assert briefing.grounded_answers[0].evidence_sufficient is False
    assert "not found" in briefing.grounded_answers[0].answer


def test_scenario_f_unsupported_question_graceful_handling(db):
    """Scenario F2: Unsupported or speculative questions return evidence_sufficient=False
    and explicitly list supported questions without fabricating answers.
    """
    unsupported_query = "What will the temperature and weather be in Ripple City tomorrow?"
    briefing = run_investigation_agent("SUB-001", question=unsupported_query, persist_memory=False, client=db)

    assert len(briefing.grounded_answers) == 1
    ans = briefing.grounded_answers[0]
    assert ans.evidence_sufficient is False
    assert ans.confidence_score == 0.0
    assert "relies strictly on deterministic graph evidence" in ans.answer
    assert "Supported inquiry categories:" in ans.answer
    assert ans.supporting_asset_ids == []
    assert ans.graph_paths == []


# =============================================================================
# SCENARIO G: Recovery Ranking Explanation
# =============================================================================

def test_scenario_g_recovery_ranking_explanation_grounding(db):
    """Scenario G: Explains top-ranked recovery plan using actual score breakdown,
    time assumptions, protected and partially mitigated assets, and trade-offs.
    """
    question = "Why is this recovery plan ranked first?"
    briefing = run_investigation_agent("SUB-001", question=question, persist_memory=False, client=db)

    ans = briefing.grounded_answers[0]
    assert ans.evidence_sufficient is True
    assert ans.confidence_score == 1.0

    rec_plan = briefing.recommended_plan
    assert rec_plan is not None

    # Answer text includes plan ID, composite benefit score, hours, and actions
    assert rec_plan.plan_id in ans.answer
    assert f"{rec_plan.composite_benefit_score:.1f}" in ans.answer
    assert f"{rec_plan.total_estimated_hours:.1f}" in ans.answer
    assert len(ans.supporting_asset_ids) > 0
    assert len(ans.relevant_properties) > 0


# =============================================================================
# SCENARIO H: Graph Integrity & Status Preservation
# =============================================================================

def test_scenario_h_graph_integrity_and_status_preservation(db):
    """Scenario H: Confirms that running the agent (both read-only and with explicit persistence)
    NEVER mutates infrastructure node operational statuses (n.status).
    """
    # 1. Snapshot operational statuses across all InfrastructureNodes
    status_snapshot_query = "MATCH (n:InfrastructureNode) RETURN n.id, n.status ORDER BY n.id"
    initial_statuses = db.query(status_snapshot_query)
    assert len(initial_statuses) > 0

    # 2. Run read-only agent
    run_investigation_agent("SUB-001", persist_memory=False, client=db)
    statuses_after_readonly = db.query(status_snapshot_query)
    assert statuses_after_readonly == initial_statuses, "Read-only agent mutated infrastructure node operational statuses!"

    # 3. Run explicit write agent
    test_id = "INC-TEST-INTEGRITY-001"
    run_investigation_agent("SUB-001", persist_memory=True, incident_id=test_id, client=db)
    statuses_after_write = db.query(status_snapshot_query)
    assert statuses_after_write == initial_statuses, "Explicit memory write mutated infrastructure node operational statuses!"

    # Clean up test incident
    db.query("""
    MATCH (inc:Incident {id: $inc_id})
    OPTIONAL MATCH (inc)-[:USED_ACTION]->(act:RecoveryAction)
    OPTIONAL MATCH (inc)-[:SUPPORTED_BY]->(evd:EvidenceRecord)
    DETACH DELETE inc, act, evd
    """, {"inc_id": test_id})


# =============================================================================
# GROUNDED QUESTIONS SUITE: All 6 Documented Questions
# =============================================================================

@pytest.mark.parametrize("question_text", [
    "What could be affected if SUB-001 fails?",
    "Which critical services have no viable alternate supply?",
    "What previous incidents involved this component?",
    "Why is this recovery plan ranked first?",
    "Which risks remain after the proposed intervention?",
    "What information is missing before we can recommend an action confidently?",
])
def test_all_six_grounded_questions(question_text, db):
    """Verifies that all 6 questions produce evidence-grounded, non-empty answers
    with valid supporting asset IDs, assumptions, and confidence scores.
    """
    briefing = run_investigation_agent("SUB-001", question=question_text, persist_memory=False, client=db)

    assert len(briefing.grounded_answers) == 1
    ans = briefing.grounded_answers[0]
    assert ans.evidence_sufficient is True
    assert ans.confidence_score > 0.8
    assert len(ans.answer) > 30
    assert isinstance(ans.supporting_asset_ids, list)
    assert isinstance(ans.graph_paths, list)
    assert isinstance(ans.unresolved_assumptions, list)


def test_recommended_and_simulated_never_upgraded_to_confirmed():
    """Regression test: Verify that RECOMMENDED, PROPOSED, SIMULATED, or unrecorded
    actions are NEVER classified as CONFIRMED_SUCCESSFUL even if notes mention success.
    """
    speculative_statuses = [
        "RECOMMENDED",
        "PROPOSED",
        "SIMULATED",
        "SHADOW_SIMULATED",
        "PLANNED",
        None,
        "",
    ]
    for s in speculative_statuses:
        type_, desc_ = classify_action_outcome(s, notes="Verified 100% operational success and recovery")
        assert type_ != OutcomeType.CONFIRMED_SUCCESSFUL, f"Status '{s}' was upgraded to CONFIRMED_SUCCESSFUL!"
        assert type_ != OutcomeType.CONFIRMED_FAILED, f"Status '{s}' was upgraded to CONFIRMED_FAILED!"


def test_canonical_scoring_identity(db):
    """Regression test: Verify that agent's RippleScores are identical in value and order
    to the canonical compute_incident_ripple_scores module without duplicated formulas.
    """
    from app.impact_engine import investigate_incident
    from app.ripple_score import compute_incident_ripple_scores

    inv = investigate_incident("SUB-001", client=db)
    canonical = compute_incident_ripple_scores(inv, client=db)
    briefing = run_investigation_agent("SUB-001", persist_memory=False, client=db)

    assert len(canonical.ranked_scores) == len(briefing.ripple_scores)
    for c, a in zip(canonical.ranked_scores, briefing.ripple_scores):
        assert c.asset_id == a.asset_id
        assert c.total_score == a.total_score
        assert c.inherent_score == a.inherent_score
        assert c.downstream_impact_score == a.downstream_impact_score
        assert c.multipath_vulnerability_score == a.multipath_vulnerability_score
        assert c.spof_penalty == a.spof_penalty
        assert c.mitigation_credit == a.mitigation_credit
        assert c.backup_credit == a.backup_credit
        assert c.capacity_penalty == a.capacity_penalty
        assert c.failed_contingency_penalty == a.failed_contingency_penalty

