"""Investigation Agent for RippleMap.

Coordinates graph traversal, incident memory retrieval, transparent RippleScore risk ranking,
and grounded recovery plan optimization.
Operates deterministically without requiring an external LLM API key.
"""

import re
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from app.db import FalkorDBClient, db_client
from app.graph_queries import validate_node_id, get_node_by_id
from app.impact_engine import investigate_incident
from app.ripple_score import compute_incident_ripple_scores
from app.recovery_optimizer import optimize_recovery_plans
from app.incident_memory import query_incident_memory, record_investigation_memory
from app.groq_client import generate_briefing_narrative, generate_question_narrative
from app.schema import (
    ImpactClassification,
    AffectedAssetFinding,
    EvidencePath,
    ScoreBreakdown,
    HistoricalIncidentMatch,
    CandidateAction,
    RecoveryPlan,
    OptimizationResult,
    InvestigationResult,
    GroundedAnswer,
    AgentBriefing,
)

logger = logging.getLogger(__name__)


def answer_grounded_question(
    question: str,
    investigation: InvestigationResult,
    memory: list[HistoricalIncidentMatch],
    scores: list[ScoreBreakdown],
    optimization: OptimizationResult,
) -> GroundedAnswer:
    """Evaluates an evidence-grounded question deterministically against graph state,
    incident memory, RippleScores, and recovery plans.
    
    If graph evidence is insufficient or question is unsupported, explicitly returns
    evidence_sufficient=False without fabricating facts.
    """
    q_norm = question.strip().lower()
    source_id = investigation.source_node_id

    # -------------------------------------------------------------------------
    # Question 1: What could be affected if <ID> fails?
    # -------------------------------------------------------------------------
    if "affected" in q_norm and ("fail" in q_norm or "outage" in q_norm or "what could be" in q_norm or "what is" in q_norm):
        direct = [f for f in investigation.affected_services if f.direct_distance == 1]
        downstream = [f for f in investigation.affected_services if f.direct_distance > 1]
        crit_services = [f for f in investigation.affected_services if "Tier 1" in f.criticality or "Tier 2" in f.criticality]

        direct_ids = [d.asset_id for d in direct]
        downstream_ids = [d.asset_id for d in downstream]
        crit_ids = [c.asset_id for c in crit_services]

        path_summaries = []
        for f in investigation.affected_services:
            for ep in f.evidence_paths:
                path_summaries.append(ep.summary)

        answer_text = (
            f"If {investigation.source_node_name} ({source_id}) fails, a total of {investigation.total_affected_count} "
            f"infrastructure assets are reachable in the failure cascade across {investigation.critical_services_count} critical services.\n"
            f"• Direct Dependencies ({len(direct)}): {', '.join(direct_ids) or 'None'}\n"
            f"• Downstream Cascades ({len(downstream)}): {', '.join(downstream_ids) or 'None'}\n"
            f"• Critical Life Safety / Essential Services ({len(crit_services)}): {', '.join(crit_ids) or 'None'}"
        )

        return GroundedAnswer(
            question=question,
            answer=answer_text,
            supporting_asset_ids=[f.asset_id for f in investigation.affected_services],
            graph_paths=path_summaries[:5],
            relationship_types=["SUPPLIES_POWER_TO", "SUPPLIES_WATER_TO", "SUPPORTS_COMMUNICATION_FOR", "CONNECTS_TO"],
            relevant_properties={
                "total_affected_count": investigation.total_affected_count,
                "critical_services_count": investigation.critical_services_count,
                "direct_dependency_count": len(direct),
            },
            unresolved_assumptions=[
                "Assumes total loss of primary power/water feeder from source without instantaneous automated isolation.",
            ],
            evidence_sufficient=True,
            confidence_score=1.0,
        )

    # -------------------------------------------------------------------------
    # Question 2: Which critical services have no viable alternate supply?
    # -------------------------------------------------------------------------
    if "alternate supply" in q_norm or "alternate route" in q_norm or "no viable" in q_norm or "no alternate" in q_norm:
        unmitigated_critical: list[AffectedAssetFinding] = []
        for f in investigation.affected_services:
            if ("Tier 1" in f.criticality or "Tier 2" in f.criticality) and not f.alternate_supply_available:
                unmitigated_critical.append(f)

        supporting_ids = [f.asset_id for f in unmitigated_critical]
        bullet_points = []
        for f in unmitigated_critical:
            backup_note = "No backup generator"
            if f.backup_available:
                gen_id = f.backup_details[0].get("generator_id") or f.backup_details[0].get("id", "GEN")
                backup_note = f"Backup generator available ({gen_id})"
                if f.classification == ImpactClassification.BACKUP_CAPACITY_INSUFFICIENT:
                    backup_note += " but has insufficient capacity rating"
                elif f.classification == ImpactClassification.BACKUP_UNAVAILABLE:
                    backup_note += " but is FAILED/UNAVAILABLE"
            bullet_points.append(f"• {f.asset_name} ({f.asset_id}) [{f.criticality}]: {backup_note}")

        answer_text = (
            f"There are {len(unmitigated_critical)} critical Tier 1/Tier 2 services with no viable alternate supply routes:\n"
            + "\n".join(bullet_points)
        )

        return GroundedAnswer(
            question=question,
            answer=answer_text,
            supporting_asset_ids=supporting_ids,
            graph_paths=[ep.summary for f in unmitigated_critical for ep in f.evidence_paths][:5],
            relationship_types=["SUPPLIES_POWER_TO", "SUPPLIES_WATER_TO", "HAS_BACKUP"],
            relevant_properties={
                "unmitigated_critical_count": len(unmitigated_critical),
                "unmitigated_critical_ids": supporting_ids,
            },
            unresolved_assumptions=[
                "Backup generators, where present, depend on verified on-site fuel stores and operational transfer switches.",
            ],
            evidence_sufficient=True,
            confidence_score=0.95,
        )

    # -------------------------------------------------------------------------
    # Question 3: What previous incidents involved this component?
    # -------------------------------------------------------------------------
    if "previous incident" in q_norm or "prior incident" in q_norm or "history" in q_norm or "involved this component" in q_norm:
        if not memory:
            return GroundedAnswer(
                question=question,
                answer=f"No prior incidents involving component {source_id} or its cascade dependencies were found in FalkorDB incident memory.",
                supporting_asset_ids=[],
                graph_paths=[],
                relationship_types=["TRIGGERED_BY", "AFFECTED", "USED_ACTION", "SUPPORTED_BY"],
                relevant_properties={"historical_incident_count": 0},
                unresolved_assumptions=[],
                evidence_sufficient=False,
                confidence_score=1.0,
            )

        bullet_points = []
        supporting_ids = set()
        supporting_paths = []
        for m in memory:
            supporting_ids.add(m.incident_id)
            supporting_ids.update(m.matching_assets)
            if m.evidence_path_summary:
                supporting_paths.append(m.evidence_path_summary)

            action_info = "No recovery action recorded"
            if m.recovery_action_name:
                action_info = (
                    f"Action: '{m.recovery_action_name}' ({m.recovery_action_id}) | "
                    f"Status: {m.action_status} [{m.outcome_type.value}] - {m.outcome_description}"
                )

            bullet_points.append(
                f"• [{m.incident_id}] '{m.title}' ({m.timestamp[:10]})\n"
                f"  - Relevance: {m.relevance_reason}\n"
                f"  - Severity: {m.severity} | Simulated: {m.simulated}\n"
                f"  - {action_info}"
            )

        answer_text = (
            f"FalkorDB incident memory identified {len(memory)} historical record(s) relevant to {source_id}:\n"
            + "\n".join(bullet_points)
        )

        return GroundedAnswer(
            question=question,
            answer=answer_text,
            supporting_asset_ids=sorted(list(supporting_ids)),
            graph_paths=supporting_paths,
            relationship_types=["TRIGGERED_BY", "AFFECTED", "USED_ACTION", "SUPPORTED_BY"],
            relevant_properties={
                "incident_count": len(memory),
                "incident_ids": [m.incident_id for m in memory],
            },
            unresolved_assumptions=[
                "Historical outcomes reflect recorded field execution where explicitly confirmed (e.g. EXECUTED_SUCCESSFUL); "
                "proposed actions have no guaranteed real-world execution.",
            ],
            evidence_sufficient=True,
            confidence_score=1.0,
        )

    # -------------------------------------------------------------------------
    # Question 4: Why is this recovery plan ranked first?
    # -------------------------------------------------------------------------
    if "ranked first" in q_norm or "why is this" in q_norm or "top recovery plan" in q_norm or "top-ranked" in q_norm or "ranking rationale" in q_norm:
        plan = optimization.recommended_plan
        if not plan:
            return GroundedAnswer(
                question=question,
                answer="No recovery plans could be generated or recommended from the current graph topology.",
                supporting_asset_ids=[],
                graph_paths=[],
                relationship_types=[],
                relevant_properties={},
                unresolved_assumptions=[],
                evidence_sufficient=False,
                confidence_score=0.0,
            )

        action_names = [f"'{a.action_type}' targeting {a.target_id} ({a.estimated_hours}h)" for a in plan.actions]
        explanation = (
            f"Plan '{plan.plan_name}' ({plan.plan_id}) is ranked #1 with a composite benefit score of {plan.composite_benefit_score:.1f}.\n"
            f"• Unique Critical Services Protected: {plan.unique_critical_services_protected} of {optimization.baseline_critical_count}\n"
            f"• Total Execution Window: {plan.total_estimated_hours:.1f} hours\n"
            f"• Actions ({len(plan.actions)}): {'; '.join(action_names)}\n"
            f"• Fully Protected Assets: {', '.join(plan.fully_protected_asset_ids) or 'None'}\n"
            f"• Partially Mitigated Assets: {', '.join(plan.partially_mitigated_asset_ids) or 'None'}\n"
            f"• Rationale: {optimization.recommendation_rationale}"
        )

        return GroundedAnswer(
            question=question,
            answer=explanation,
            supporting_asset_ids=plan.protected_asset_ids,
            graph_paths=[f"{a.supplier_id or 'LOCAL'} -> {a.target_id}" for a in plan.actions],
            relationship_types=["SUPPLIES_POWER_TO", "HAS_BACKUP", "CONNECTS_TO"],
            relevant_properties={
                "composite_benefit_score": plan.composite_benefit_score,
                "total_estimated_hours": plan.total_estimated_hours,
                "unique_critical_services_protected": plan.unique_critical_services_protected,
                "residual_affected_count": plan.residual_affected_count,
            },
            unresolved_assumptions=[
                "Assumes parallel execution across independent utility, road, and water crews.",
                "Assumes operational switchgear and capacity headroom at supplier nodes.",
            ],
            evidence_sufficient=True,
            confidence_score=1.0,
        )

    # -------------------------------------------------------------------------
    # Question 5: Which risks remain after the proposed intervention?
    # -------------------------------------------------------------------------
    if "risks remain" in q_norm or "residual" in q_norm or "remaining" in q_norm or "unresolved" in q_norm:
        plan = optimization.recommended_plan
        if not plan:
            return GroundedAnswer(
                question=question,
                answer="No recovery plan is active to evaluate residual exposure.",
                supporting_asset_ids=[],
                graph_paths=[],
                relationship_types=[],
                relevant_properties={},
                unresolved_assumptions=[],
                evidence_sufficient=False,
                confidence_score=0.0,
            )

        tradeoffs = "\n".join([f"• {t}" for t in plan.tradeoffs_and_risks])
        answer_text = (
            f"After executing '{plan.plan_name}' ({plan.plan_id}), the following residual risks and exposures remain:\n"
            f"• Residual Affected Assets ({plan.residual_affected_count}): {', '.join(plan.unresolved_asset_ids) or 'None'}\n"
            f"• Residual Critical Services: {plan.residual_critical_count}\n"
            f"• Partially Mitigated Assets ({len(plan.partially_mitigated_asset_ids)}): {', '.join(plan.partially_mitigated_asset_ids) or 'None'}\n"
            f"Trade-offs & Operational Limitations:\n{tradeoffs}"
        )

        return GroundedAnswer(
            question=question,
            answer=answer_text,
            supporting_asset_ids=plan.unresolved_asset_ids + plan.partially_mitigated_asset_ids,
            graph_paths=[],
            relationship_types=["SUPPLIES_POWER_TO", "SUPPLIES_WATER_TO"],
            relevant_properties={
                "residual_affected_count": plan.residual_affected_count,
                "residual_critical_count": plan.residual_critical_count,
                "partially_mitigated_count": len(plan.partially_mitigated_asset_ids),
            },
            unresolved_assumptions=[
                "Downstream telemetry restoration (e.g. mobile tower) does NOT restore heavy electrical or water pump dependencies.",
            ],
            evidence_sufficient=True,
            confidence_score=1.0,
        )

    # -------------------------------------------------------------------------
    # Question 6: What information is missing before we can recommend an action confidently?
    # -------------------------------------------------------------------------
    if "missing" in q_norm or "confidence" in q_norm or "confidently" in q_norm or "assumptions" in q_norm:
        missing_notes = []
        low_confidence_assets = []
        for s in scores:
            if s.missing_data_notes:
                missing_notes.extend([f"{s.asset_name} ({s.asset_id}): {note}" for note in s.missing_data_notes])
            if s.confidence < 1.0:
                low_confidence_assets.append(f"{s.asset_name} ({s.asset_id}) [confidence: {s.confidence:.2f}]")

        general_gaps = [
            "Real-time operational headroom on supplier substations (e.g. SUB-002) is unmetered in static graph topology.",
            "Field fuel reserve levels and actual runtime under continuous load on backup generators (GEN-001, GEN-002, GEN-003) require physical dipstick confirmation.",
            "Transfer switch switchgear synchronization status at secondary nodes must be verified prior to energization.",
            "Field crew availability and dispatch transit latency under road disruptions are modeled as static estimates.",
        ]

        answer_text = (
            f"Before executing high-impact recovery plans, the following information gaps and assumptions must be verified:\n"
            f"1. Property & Operational Gaps:\n"
            + "\n".join([f"• {g}" for g in general_gaps]) + "\n"
            f"2. Asset-Specific Data Confidence Limitations:\n"
            + ("\n".join([f"• {a}" for a in low_confidence_assets]) if low_confidence_assets else "• All scored assets have full property records.")
        )

        return GroundedAnswer(
            question=question,
            answer=answer_text,
            supporting_asset_ids=[s.asset_id for s in scores if s.confidence < 1.0],
            graph_paths=[],
            relationship_types=[],
            relevant_properties={"scored_asset_count": len(scores)},
            unresolved_assumptions=general_gaps,
            evidence_sufficient=True,
            confidence_score=0.90,
        )

    # -------------------------------------------------------------------------
    # Unsupported Question Fallback
    # -------------------------------------------------------------------------
    fallback_text = (
        f"The RippleMap investigation agent relies strictly on deterministic graph evidence and cannot "
        f"answer '{question}' without verifiable graph data.\n\n"
        f"Supported inquiry categories:\n"
        f"1. Blast radius & cascades: 'What could be affected if {source_id} fails?'\n"
        f"2. Supply vulnerability: 'Which critical services have no viable alternate supply?'\n"
        f"3. Incident memory: 'What previous incidents involved this component?'\n"
        f"4. Plan justification: 'Why is this recovery plan ranked first?'\n"
        f"5. Residual exposure: 'Which risks remain after the proposed intervention?'\n"
        f"6. Data confidence: 'What information is missing before we can recommend an action confidently?'"
    )

    return GroundedAnswer(
        question=question,
        answer=fallback_text,
        supporting_asset_ids=[],
        graph_paths=[],
        relationship_types=[],
        relevant_properties={},
        unresolved_assumptions=["Question outside supported deterministic Cypher query domain."],
        evidence_sufficient=False,
        confidence_score=0.0,
    )


def run_investigation_agent(
    source_id: str,
    question: Optional[str] = None,
    persist_memory: bool = False,
    incident_id: Optional[str] = None,
    use_llm: bool = True,
    client: Optional[FalkorDBClient] = None,
) -> AgentBriefing:
    """Master orchestration function for the RippleMap investigation agent.
    
    Coordinates:
    1. Source validation and context retrieval.
    2. Deterministic cascade investigation (app.impact_engine).
    3. Historical incident memory retrieval (app.incident_memory).
    4. Transparent RippleScore ranking (app.ripple_score).
    5. Grounded recovery plan optimization (app.recovery_optimizer).
    6. Evidence-grounded question evaluation.
    7. Safe, optional memory persistence (app.incident_memory).
    
    Zero external LLM API key required.
    Strictly read-only unless persist_memory=True is explicitly passed.
    """
    db = client or db_client
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Source Validation
    try:
        clean_id = validate_node_id(source_id)
        source_node = get_node_by_id(clean_id, client=db)
    except Exception as e:
        source_node = None
        clean_id = source_id

    if not source_node:
        logger.warning(f"Investigation source '{clean_id}' not found in infrastructure graph.")
        unsupported_ans = GroundedAnswer(
            question=question or "Status Check",
            answer=f"Source component '{clean_id}' was not found in the Ripple City infrastructure graph.",
            supporting_asset_ids=[],
            graph_paths=[],
            relationship_types=[],
            relevant_properties={},
            unresolved_assumptions=["Component ID does not exist in graph database."],
            evidence_sufficient=False,
            confidence_score=0.0,
        )
        return AgentBriefing(
            incident_id=incident_id or f"INC-UNKNOWN-{clean_id}",
            source_node_id=clean_id,
            source_node_name=f"Unknown Component ({clean_id})",
            source_entity_type="Unknown",
            source_criticality="Unknown",
            source_status="UNKNOWN",
            timestamp=now_iso,
            is_persisted_memory=False,
            investigation_summary=f"Investigation failed: source node '{clean_id}' not found in FalkorDB graph.",
            direct_findings=[],
            downstream_findings=[],
            evidence_paths=[],
            ripple_scores=[],
            historical_incidents=[],
            candidate_actions=[],
            evaluated_plans=[],
            recommended_plan=None,
            recommendation_rationale="No recovery plans available for non-existent component.",
            grounded_answers=[unsupported_ans],
            recommended_next_steps=["Verify component identifier against valid infrastructure nodes."],
            missing_data_and_assumptions=["Node missing from property graph."],
            confidence_assessment={"overall_confidence": 0.0, "status": "INVALID_SOURCE"},
            memory_persistence_details=None,
        )

    # 2. Run Deterministic Investigation Engine
    investigation = investigate_incident(clean_id, client=db)

    # 3. Retrieve Historical Incident Memory
    affected_ids = [f.asset_id for f in investigation.affected_services]
    historical_memory = query_incident_memory(clean_id, affected_asset_ids=affected_ids, client=db)

    # 4. Compute Transparent RippleScores
    ripple_score_result = compute_incident_ripple_scores(investigation, client=db)

    # 5. Evaluate Recovery Plans
    optimization_result = optimize_recovery_plans(investigation, client=db)

    # Separate direct and downstream findings for clear briefing structure
    direct_findings = [f for f in investigation.affected_services if f.direct_distance == 1]
    downstream_findings = [f for f in investigation.affected_services if f.direct_distance > 1]

    all_evidence_paths: list[EvidencePath] = []
    for f in investigation.affected_services:
        all_evidence_paths.extend(f.evidence_paths)

    # 6. Evaluate Grounded Questions
    grounded_answers: list[GroundedAnswer] = []
    if question:
        ans = answer_grounded_question(
            question=question,
            investigation=investigation,
            memory=historical_memory,
            scores=ripple_score_result.ranked_scores,
            optimization=optimization_result,
        )
        grounded_answers.append(ans)
    else:
        # Default briefing Q&A answering core operational questions
        q1 = answer_grounded_question(
            f"What could be affected if {clean_id} fails?",
            investigation, historical_memory, ripple_score_result.ranked_scores, optimization_result
        )
        q2 = answer_grounded_question(
            "Why is this recovery plan ranked first?",
            investigation, historical_memory, ripple_score_result.ranked_scores, optimization_result
        )
        grounded_answers.extend([q1, q2])

    # 7. Synthesize Grounded Next Steps
    recommended_steps: list[str] = []
    if optimization_result.recommended_plan:
        rec_plan = optimization_result.recommended_plan
        recommended_steps.append(
            f"Execute recovery plan '{rec_plan.plan_name}' ({rec_plan.plan_id}): expected duration "
            f"{rec_plan.total_estimated_hours:.1f}h, protecting {rec_plan.unique_critical_services_protected} critical services."
        )
        for act in rec_plan.actions:
            recommended_steps.append(f"• Deploy {act.action_type}: {act.description}")

    # Add field check recommendations for vulnerable assets
    for alert in investigation.backup_alerts:
        recommended_steps.append(f"Field Alert: {alert.get('message', 'Verify backup system status')}")

    if ripple_score_result.ranked_scores:
        top_risk = ripple_score_result.ranked_scores[0]
        recommended_steps.append(
            f"Prioritize continuous telemetry monitoring on highest exposure component: {top_risk.asset_name} "
            f"({top_risk.asset_id}) [RippleScore: {top_risk.total_score:.1f}/100]."
        )

    # 8. Safe Memory Persistence (Explicit Only)
    persistence_details = None
    is_persisted = False
    if persist_memory:
        persistence_details = record_investigation_memory(
            investigation=investigation,
            ripple_scores=ripple_score_result.ranked_scores,
            recovery_plan=optimization_result.recommended_plan,
            incident_id=incident_id,
            client=db,
        )
        is_persisted = True

    # 9. Confidence and Limitation Assessment
    avg_confidence = (
        sum(s.confidence for s in ripple_score_result.ranked_scores) / len(ripple_score_result.ranked_scores)
        if ripple_score_result.ranked_scores else 1.0
    )
    confidence_assessment = {
        "overall_data_confidence": round(avg_confidence, 2),
        "scored_asset_count": len(ripple_score_result.ranked_scores),
        "historical_memory_records_found": len(historical_memory),
        "feasible_plans_count": len(optimization_result.evaluated_plans),
        "is_read_only_mode": not persist_memory,
    }

    # Consolidated missing data & assumptions
    consolidated_assumptions = list(investigation.assumptions)
    consolidated_assumptions.extend(optimization_result.assumptions)
    for score in ripple_score_result.ranked_scores:
        consolidated_assumptions.extend(score.missing_data_notes)
    # Deduplicate while preserving order
    unique_assumptions = list(dict.fromkeys(consolidated_assumptions))

    # Comprehensive summary
    briefing_summary = (
        f"Investigation Briefing for {source_node['name']} ({clean_id}) [{source_node['criticality']}]. "
        f"Cascading failure reaches {investigation.total_affected_count} assets across "
        f"{investigation.critical_services_count} critical services. "
        f"FalkorDB memory matched {len(historical_memory)} relevant historical record(s). "
        f"Recovery optimizer evaluated {len(optimization_result.evaluated_plans)} candidate plan(s); "
        f"recommended: '{optimization_result.recommended_plan.plan_name if optimization_result.recommended_plan else 'None'}'. "
        f"Memory persistence: {'PERSISTED' if is_persisted else 'READ_ONLY'}."
    )

    briefing = AgentBriefing(
        incident_id=incident_id or investigation.incident_id,
        source_node_id=clean_id,
        source_node_name=source_node["name"],
        source_entity_type=source_node["entity_type"],
        source_criticality=source_node["criticality"],
        source_status=source_node["status"],
        timestamp=now_iso,
        is_persisted_memory=is_persisted,
        investigation_summary=briefing_summary,
        direct_findings=direct_findings,
        downstream_findings=downstream_findings,
        evidence_paths=all_evidence_paths,
        ripple_scores=ripple_score_result.ranked_scores,
        historical_incidents=historical_memory,
        candidate_actions=optimization_result.candidate_actions,
        evaluated_plans=optimization_result.evaluated_plans,
        recommended_plan=optimization_result.recommended_plan,
        recommendation_rationale=optimization_result.recommendation_rationale,
        grounded_answers=grounded_answers,
        recommended_next_steps=recommended_steps,
        missing_data_and_assumptions=unique_assumptions,
        confidence_assessment=confidence_assessment,
        memory_persistence_details=persistence_details,
        llm_narrative=None,
        llm_explanation_status="DETERMINISTIC_ONLY",
    )

    # 10. Optional Groq Natural-Language Explanation Layer
    if use_llm:
        narrative, status = generate_briefing_narrative(briefing)
        briefing.llm_narrative = narrative
        briefing.llm_explanation_status = status

        # If a specific question was asked, generate narrative explanation for the question answer
        if question and grounded_answers:
            q_narrative, _ = generate_question_narrative(question, grounded_answers[0])
            grounded_answers[0].llm_explanation = q_narrative

    return briefing

