"""Integration test suite for RippleScore risk ranking and Recovery Optimizer.

Tests deterministic scoring formulas, confidence calibration, candidate action grounding,
plan comparison, deduplicated benefit accounting, and zero-mutation graph safety against live FalkorDB.
"""

import pytest
from app.db import db_client
from app.schema import ImpactClassification, InvestigationResult, OptimizationResult, RippleScoreResult
from app.impact_engine import investigate_incident
from app.ripple_score import calculate_component_score, compute_incident_ripple_scores
from app.recovery_optimizer import generate_candidate_actions, evaluate_recovery_plans, calculate_intervention_benefit


def test_ripple_score_formula_weights():
    """Verify that calculate_component_score applies documented weights and clamping."""
    # Test Tier 1 Life Safety component with downstream impact
    score_t1 = calculate_component_score(
        node_id="TEST-001",
        node_name="Test Trauma Center",
        criticality="Tier 1 - Life Safety",
        is_source=False,
        is_spof=False,
        downstream_nodes=[{"id": "CHILD-01", "criticality": "Tier 1 - Life Safety"}],
        incoming_paths=[],
    )
    assert score_t1.inherent_score == 40.0
    assert score_t1.downstream_impact_score == 10.0
    assert score_t1.total_score == 50.0
    assert score_t1.confidence == 1.0

    # Test clamping: negative inputs should not produce negative total score
    score_clamped_low = calculate_component_score(
        node_id="TEST-002",
        node_name="Test Standard Node",
        criticality="Tier 4 - Standard",
        is_source=False,
        is_spof=False,
        downstream_nodes=[],
        incoming_paths=[],
        alternate_supplies=[{"rel_type": "SUPPLIES_POWER_TO", "is_viable": True}],
        backups=[{"status": "OPERATIONAL", "buffer_hours": 10.0, "is_ready": True, "capacity_rating": "500 kW"}],
    )
    # Inherent 5 - Mitigation 20 - Backup 15 = -30 -> clamped to 0.0
    assert score_clamped_low.total_score == 0.0


def test_ripple_score_spof_and_multipath_penalties():
    """Verify that shared upstream SPOF status and multi-vector exposures add penalties."""
    # SPOF Root Node
    score_spof = calculate_component_score(
        node_id="SUB-001",
        node_name="Metro Central Substation",
        criticality="Tier 1 - Life Safety",
        is_source=True,
        is_spof=True,
        downstream_nodes=[
            {"id": f"NODE-{i}", "criticality": "Tier 1 - Life Safety"} for i in range(5)
        ],
    )
    assert score_spof.inherent_score == 40.0
    assert score_spof.downstream_impact_score == 35.0  # Capped at 35
    assert score_spof.spof_penalty == 10.0
    assert score_spof.total_score == 85.0


def test_ripple_score_missing_data_confidence_deductions():
    """Verify that missing capacity ratings or uncalibrated data lower confidence score."""
    score_uncertain = calculate_component_score(
        node_id="TEST-UNCERTAIN",
        node_name="Uncertain Node",
        criticality="Tier 2 - Essential Service",
        is_source=False,
        backups=[{
            "generator_id": "GEN-UNCERTAIN",
            "status": "OPERATIONAL",
            "capacity_rating": "",  # Empty capacity rating
            "buffer_hours": 5.0,
            "has_uncertain_capacity": True,
        }],
    )
    assert score_uncertain.confidence < 1.0
    assert any("uncertainty" in note for note in score_uncertain.missing_data_notes)


def test_incident_ripple_scores_for_sub001():
    """Verify end-to-end RippleScore ranking for SUB-001 incident investigation."""
    inv = investigate_incident("SUB-001")
    scores_res = compute_incident_ripple_scores(inv)

    assert isinstance(scores_res, RippleScoreResult)
    assert len(scores_res.ranked_scores) == inv.total_affected_count + 1  # Source + affected
    assert scores_res.ranked_scores[0].asset_id == "SUB-001"
    assert scores_res.ranked_scores[0].total_score >= 80.0

    # Verify scores are strictly ordered descending
    for i in range(len(scores_res.ranked_scores) - 1):
        assert scores_res.ranked_scores[i].total_score >= scores_res.ranked_scores[i + 1].total_score


def test_candidate_action_generation_grounding():
    """Verify all candidate recovery actions are derived from database relationships."""
    inv = investigate_incident("SUB-001")
    feasible, rejected = generate_candidate_actions(inv)

    assert len(feasible) >= 5
    action_types = {a.action_type for a in feasible}
    assert "RESTORE_COMPONENT" in action_types
    assert "SWITCH_ALTERNATE_SUPPLY" in action_types
    assert "DEPLOY_BACKUP" in action_types

    # Ensure every feasible action has non-empty preconditions
    for a in feasible:
        assert len(a.preconditions) >= 1
        assert a.estimated_hours > 0.0


def test_failed_backup_rejection_in_optimizer():
    """Verify that GEN-005 (failed starter motor) is rejected by the optimizer in SUB-003 cascade."""
    inv3 = investigate_incident("SUB-003")
    feasible, rejected = generate_candidate_actions(inv3)

    gen5_rejected = next(
        (r for r in rejected if r.target_id == "CLINIC-003" and r.supplier_id == "GEN-005"), None
    )
    assert gen5_rejected is not None
    assert gen5_rejected.is_feasible is False
    assert "FAILED" in gen5_rejected.rejection_reason


def test_insufficient_capacity_action_warning():
    """Verify that GEN-002 (1.2 MW mobile trailer) is flagged with capacity warning (40%)."""
    inv = investigate_incident("SUB-001")
    feasible, _ = generate_candidate_actions(inv)

    pump_backup_act = next(
        (a for a in feasible if a.target_id == "PUMP-001" and a.supplier_id == "GEN-002"), None
    )
    assert pump_backup_act is not None
    assert pump_backup_act.has_capacity_warning is True
    assert pump_backup_act.capacity_ratio == 0.40


def test_telecom_tie_line_recovery_action():
    """Verify that the auxiliary tie-line action SUB-002 -> TOWER-001 restores communications."""
    inv = investigate_incident("SUB-001")
    feasible, _ = generate_candidate_actions(inv)

    tie_line_act = next(
        (a for a in feasible if a.target_id == "TOWER-001" and a.supplier_id == "SUB-002"), None
    )
    assert tie_line_act is not None
    assert tie_line_act.estimated_hours == 1.0
    assert tie_line_act.dependency_type == "auxiliary_tie_line"
    assert "TOWER-001" in tie_line_act.protected_asset_ids
    # Restoring TOWER-001 protects downstream CAD dispatch at EMERG-001
    assert "EMERG-001" in tie_line_act.protected_asset_ids


def test_recovery_plan_comparison_and_deduplication():
    """Verify that multi-action plans deduplicate protected assets without double-counting."""
    inv = investigate_incident("SUB-001")
    feasible, rejected = generate_candidate_actions(inv)
    opt = evaluate_recovery_plans(inv, feasible + rejected)

    assert isinstance(opt, OptimizationResult)
    assert len(opt.evaluated_plans) >= 3
    assert opt.recommended_plan is not None

    # Check Plan B: Comprehensive Triage
    multi_plan = next((p for p in opt.evaluated_plans if p.plan_id == "PLAN-MULTI-002"), None)
    assert multi_plan is not None

    # Verify deduplication: protected_asset_ids must contain no duplicates
    assert len(multi_plan.protected_asset_ids) == len(set(multi_plan.protected_asset_ids))
    assert multi_plan.unique_critical_services_protected <= inv.critical_services_count


def test_zero_database_mutation():
    """Verify that RippleScore calculation and Recovery Optimization NEVER mutate FalkorDB."""
    # Capture database state before
    node_count_before = db_client.query("MATCH (n) RETURN count(n)")[0][0]
    rel_count_before = db_client.query("MATCH ()-[r]->() RETURN count(r)")[0][0]
    sub001_status_before = db_client.query("MATCH (n:Substation {id: 'SUB-001'}) RETURN n.status")[0][0]
    pump001_status_before = db_client.query("MATCH (n:WaterPump {id: 'PUMP-001'}) RETURN n.status")[0][0]

    # Run complete investigation, scoring, and optimization pipeline
    inv = investigate_incident("SUB-001")
    scores = compute_incident_ripple_scores(inv)
    feasible, rejected = generate_candidate_actions(inv)
    opt = evaluate_recovery_plans(inv, feasible + rejected)

    # Capture database state after
    node_count_after = db_client.query("MATCH (n) RETURN count(n)")[0][0]
    rel_count_after = db_client.query("MATCH ()-[r]->() RETURN count(r)")[0][0]
    sub001_status_after = db_client.query("MATCH (n:Substation {id: 'SUB-001'}) RETURN n.status")[0][0]
    pump001_status_after = db_client.query("MATCH (n:WaterPump {id: 'PUMP-001'}) RETURN n.status")[0][0]

    assert node_count_before == node_count_after, "Node count must not change!"
    assert rel_count_before == rel_count_after, "Relationship count must not change!"
    assert sub001_status_before == sub001_status_after, "SUB-001 operational status must not change!"
    assert pump001_status_before == pump001_status_after, "PUMP-001 operational status must not change!"


def test_sub001_ripple_score_reconciliation_exact_breakdown():
    """Verify that all 8 affected assets and source SUB-001 match exact formula breakdown."""
    inv = investigate_incident("SUB-001")
    score_res = compute_incident_ripple_scores(inv)
    score_map = {s.asset_id: s for s in score_res.ranked_scores}

    # Verify all 9 entities exist in ranked scores
    expected_ids = {"SUB-001", "ROAD-001", "PUMP-001", "EMERG-001", "TOWER-001", "HOSP-001", "CLINIC-001", "HOSP-002", "PUMP-002"}
    assert set(score_map.keys()) == expected_ids

    # 1. Source: SUB-001
    s_sub = score_map["SUB-001"]
    assert s_sub.inherent_score == 40.0
    assert s_sub.downstream_impact_score == 35.0  # Capped at 35.0
    assert s_sub.spof_penalty == 10.0
    assert s_sub.total_score == 85.0

    # 2. ROAD-001: 2 incoming vectors, downstream HOSP-001
    s_road = score_map["ROAD-001"]
    assert s_road.inherent_score == 40.0
    assert s_road.downstream_impact_score == 10.0
    assert s_road.multipath_vulnerability_score == 10.0
    assert s_road.total_score == 60.0

    # 3. PUMP-001: 1 incoming, downstream HOSP-001 (10) + CLINIC-001 (2) = 12, backup GEN-002 40%
    s_pump = score_map["PUMP-001"]
    assert s_pump.inherent_score == 40.0
    assert s_pump.downstream_impact_score == 12.0
    assert s_pump.multipath_vulnerability_score == 5.0
    assert s_pump.backup_credit == 6.0
    assert s_pump.capacity_penalty == 6.0
    assert s_pump.total_score == 57.0

    # 4. EMERG-001: 2 unmitigated incoming vectors
    s_emerg = score_map["EMERG-001"]
    assert s_emerg.inherent_score == 40.0
    assert s_emerg.multipath_vulnerability_score == 10.0
    assert s_emerg.total_score == 50.0

    # 5. TOWER-001: 1 incoming, mitigated by SUB-002 tie-line
    s_tower = score_map["TOWER-001"]
    assert s_tower.inherent_score == 40.0
    assert s_tower.downstream_impact_score == 30.0
    assert s_tower.mitigation_credit == 20.0
    assert s_tower.total_score == 50.0

    # 6. HOSP-001: ROAD-002 partial mitigation, GEN-001 full backup
    s_hosp1 = score_map["HOSP-001"]
    assert s_hosp1.inherent_score == 40.0
    assert s_hosp1.multipath_vulnerability_score == 10.0
    assert s_hosp1.mitigation_credit == 10.0
    assert s_hosp1.backup_credit == 15.0
    assert s_hosp1.total_score == 25.0

    # 7. CLINIC-001: Tier 3, SUB-003 partial mitigation
    s_clinic = score_map["CLINIC-001"]
    assert s_clinic.inherent_score == 12.0
    assert s_clinic.multipath_vulnerability_score == 5.0
    assert s_clinic.mitigation_credit == 10.0
    assert s_clinic.total_score == 7.0

    # 8. HOSP-002: PUMP-003 full water mitigation, GEN-003 full backup
    s_hosp2 = score_map["HOSP-002"]
    assert s_hosp2.inherent_score == 40.0
    assert s_hosp2.mitigation_credit == 20.0
    assert s_hosp2.backup_credit == 15.0
    assert s_hosp2.total_score == 5.0

    # 9. PUMP-002: Tier 3, downstream HOSP-002 (10), SUB-002 full power mitigation
    s_pump2 = score_map["PUMP-002"]
    assert s_pump2.inherent_score == 12.0
    assert s_pump2.downstream_impact_score == 10.0
    assert s_pump2.mitigation_credit == 20.0
    assert s_pump2.total_score == 2.0

    # Ensure all data confidences measure property completeness, bounded [0, 1]
    for s in score_res.ranked_scores:
        assert 0.0 <= s.confidence <= 1.0


def test_triage_plan_distinguishes_partial_and_unresolved():
    """Verify that PLAN-MULTI-002 does NOT claim partial or multi-vector assets as fully protected."""
    inv = investigate_incident("SUB-001")
    feasible, rejected = generate_candidate_actions(inv)
    opt = evaluate_recovery_plans(inv, feasible + rejected)

    triage_plan = next((p for p in opt.evaluated_plans if p.plan_id == "PLAN-MULTI-002"), None)
    assert triage_plan is not None

    # TOWER-001 is the only asset whose incoming dependencies are 100% mitigated by the tie-line
    assert "TOWER-001" in triage_plan.fully_protected_asset_ids

    # PUMP-001 (40% capacity), HOSP-001 (cooling water degraded), EMERG-001 & ROAD-001 (grid power unmitigated)
    # MUST be categorized as partially mitigated
    assert "PUMP-001" in triage_plan.partially_mitigated_asset_ids
    assert "HOSP-001" in triage_plan.partially_mitigated_asset_ids
    assert "EMERG-001" in triage_plan.partially_mitigated_asset_ids
    assert "ROAD-001" in triage_plan.partially_mitigated_asset_ids

    # CLINIC-001, HOSP-002, PUMP-002 have no actions in the triage plan and MUST be unresolved
    assert "CLINIC-001" in triage_plan.unresolved_asset_ids
    assert "HOSP-002" in triage_plan.unresolved_asset_ids
    assert "PUMP-002" in triage_plan.unresolved_asset_ids


def test_parallel_crew_resource_compatibility():
    """Verify that actions combined via max() in multi-action plans use distinct operational crews."""
    inv = investigate_incident("SUB-001")
    feasible, rejected = generate_candidate_actions(inv)
    opt = evaluate_recovery_plans(inv, feasible + rejected)

    triage_plan = next((p for p in opt.evaluated_plans if p.plan_id == "PLAN-MULTI-002"), None)
    assert triage_plan is not None

    # Verify action duration was combined using max()
    action_durations = [a.estimated_hours for a in triage_plan.actions]
    assert triage_plan.total_estimated_hours == max(action_durations)

    # Verify distinct targets and dependency types
    dep_types = [a.dependency_type for a in triage_plan.actions]
    assert len(dep_types) == len(set(dep_types)), "Parallel actions must have distinct operational domains"


def test_recovery_plan_scoring_consistency_and_asymmetry_prevention():
    """Verify consistent scoring across source restoration and multi-action plans.
    
    Catches scoring asymmetry where source restoration omits general asset coverage,
    and prevents telemetry restoration from falsely claiming full recovery of power/water.
    """
    inv = investigate_incident("SUB-001")
    feasible, rejected = generate_candidate_actions(inv)
    opt = evaluate_recovery_plans(inv, feasible + rejected)

    # 1. Source restoration must include general asset coverage (242.0, not 162.0)
    restore_act = next((a for a in feasible if a.action_id == "ACT-001"), None)
    assert restore_act is not None
    # 6 critical * 30 + 8 total * 10 - 6.0h * 3 = 180 + 80 - 18 = 242.0
    assert restore_act.net_benefit_score == 242.0
    assert restore_act.unique_critical_services_protected == 6
    assert len(restore_act.protected_asset_ids) == 8

    # 2. Winning plan is PLAN-ACT-ACT-001 with score 242.0
    assert opt.recommended_plan is not None
    assert opt.recommended_plan.plan_id == "PLAN-ACT-ACT-001"
    assert opt.recommended_plan.composite_benefit_score == 242.0
    assert opt.recommended_plan.residual_affected_count == 0
    assert opt.recommended_plan.residual_critical_count == 0

    # 3. Multi-action triage plan must score accurately (102.0, not artificially inflated to 182.0)
    # 1 full crit (30) + 4 partial crit (60) + 1 full asset (10) + 4 partial asset (20) - 2.0h * 3 (6) - 12 capacity = 102.0
    triage_plan = next((p for p in opt.evaluated_plans if p.plan_id == "PLAN-MULTI-002"), None)
    assert triage_plan is not None
    assert triage_plan.composite_benefit_score == 102.0
    assert triage_plan.composite_benefit_score < opt.recommended_plan.composite_benefit_score

    # 4. Telemetry tie-line action (ACT-003) must not claim full recovery of downstream power/water
    tie_line_act = next((a for a in feasible if a.action_id == "ACT-003"), None)
    assert tie_line_act is not None
    # 1 full crit (30) + 3 partial crit (45) + 1 full asset (10) + 3 partial asset (15) - 1.0h * 3 (3) = 97.0
    assert tie_line_act.net_benefit_score == 97.0


def test_root_restoration_graph_simulation_semantics():
    """Verify that 6h SUB-001 repair simulates in-memory path reachability and documents assumptions."""
    inv = investigate_incident("SUB-001")
    feasible, rejected = generate_candidate_actions(inv)
    opt = evaluate_recovery_plans(inv, feasible + rejected)

    plan_root = next((p for p in opt.evaluated_plans if p.plan_id == "PLAN-ACT-ACT-001"), None)
    assert plan_root is not None

    # Verify all 8 affected assets are confirmed fully protected
    assert len(plan_root.fully_protected_asset_ids) == inv.total_affected_count
    assert plan_root.residual_affected_count == 0
    assert plan_root.residual_critical_count == 0

    # Verify that the explicit idealized simulation assumption is documented
    has_sim_note = any("Simulated Root Restoration" in note for note in plan_root.tradeoffs_and_risks)
    assert has_sim_note, "Plan must document simulated root restoration assumption"
    has_cap_note = any("capacity rating" in note.lower() or "450mw" in note.lower() for note in plan_root.tradeoffs_and_risks)
    assert has_cap_note, "Plan must document primary grid capacity adequacy verification"


def test_descending_score_ordering_and_reservoir_action_tradeoff():
    """Verify all evaluated plans are strictly ordered descending by score, and verify 39.4 vs 29.5 tradeoff."""
    inv = investigate_incident("SUB-001")
    feasible, rejected = generate_candidate_actions(inv)
    opt = evaluate_recovery_plans(inv, feasible + rejected)

    # 1. Strictly ordered descending by composite_benefit_score
    for i in range(len(opt.evaluated_plans) - 1):
        assert opt.evaluated_plans[i].composite_benefit_score >= opt.evaluated_plans[i + 1].composite_benefit_score

    # 2. Re-verify the specific ranking between generator (39.4), road bypass (37.0), and reservoir (29.5)
    plan_gen = next(p for p in opt.evaluated_plans if p.plan_id == "PLAN-ACT-ACT-009")
    plan_road = next(p for p in opt.evaluated_plans if p.plan_id == "PLAN-ACT-ACT-002")
    plan_reservoir = next(p for p in opt.evaluated_plans if p.plan_id == "PLAN-ACT-ACT-004")

    assert plan_gen.composite_benefit_score == 39.4
    assert plan_road.composite_benefit_score == 37.0
    assert plan_reservoir.composite_benefit_score == 29.5

    # 3. Explainable duration tradeoff: generator is faster (0.2h vs 3.5h), avoiding 9.9pt latency penalty
    assert plan_gen.composite_benefit_score > plan_road.composite_benefit_score > plan_reservoir.composite_benefit_score
    assert plan_gen.total_estimated_hours == 0.2
    assert plan_reservoir.total_estimated_hours == 3.5


def test_recovery_benefit_formula_layering_and_no_double_counting():
    """Verify that recovery benefit scoring adheres to the layered incentive model and prevents double-counting.
    
    Proves:
    1. Algebraic identity:
       Layered Form: 30*C_full + 15*C_part + 10*A_total_full + 5*A_total_part - 3*T - penalties
       Disjoint Form: 40*C_full + 20*C_part + 10*A_standard_full + 5*A_standard_part - 3*T - penalties
       Since A_total = C + A_standard, 30*C + 10*A_total == 40*C + 10*A_standard.
    2. Critical services receive exactly 40.0 pts (10 base + 30 priority bonus).
    3. Standard non-critical assets receive exactly 10.0 pts (10 base + 0 bonus).
    4. No asset is double-counted in both standard and critical buckets under disjoint representation.
    5. All evaluated recovery plans match the disjoint model and layered model identically.
    """
    inv = investigate_incident("SUB-001")
    feasible, rejected = generate_candidate_actions(inv)
    opt = evaluate_recovery_plans(inv, feasible + rejected)

    # 1. Test canonical root restoration (ACT-001 / PLAN-ACT-ACT-001)
    # 6 critical services: HOSP-001, HOSP-002, PUMP-001, PUMP-002, TOWER-001, EMERG-001
    # 2 standard assets: CLINIC-001 (Tier 3), ROAD-001 (Tier 3)
    # Duration: 6.0h. Penalty: 0.0
    c_full = 6
    c_part = 0
    total_full = 8
    total_part = 0
    std_full = 2
    std_part = 0
    hours = 6.0

    score_layered = calculate_intervention_benefit(
        fully_protected_crit=c_full,
        partially_mitigated_crit=c_part,
        fully_protected_total=total_full,
        partially_mitigated_total=total_part,
        estimated_hours=hours,
        capacity_penalty=0.0,
    )
    # (6 * 30) + (8 * 10) - (6.0 * 3) = 180 + 80 - 18 = 242.0
    assert score_layered == 242.0

    # Disjoint calculation: 6 crit * 40 + 2 standard * 10 - 18 = 240 + 20 - 18 = 242.0
    score_disjoint = round((c_full * 40.0) + (c_part * 20.0) + (std_full * 10.0) + (std_part * 5.0) - (hours * 3.0), 1)
    assert score_disjoint == score_layered == 242.0

    # 2. Bug prevention: Ensure accidental double-bonus is rejected
    # If someone erroneously added 40 pts for critical ON TOP of total assets (yielding 50 pts/crit), score would be 302.0
    bogus_double_bonus_score = (c_full * 40.0) + (total_full * 10.0) - (hours * 3.0)
    assert score_layered != bogus_double_bonus_score
    assert bogus_double_bonus_score == 302.0

    # 3. Bug prevention: Ensure pure disjoint 30-pt critical without base coverage is rejected
    # If critical services were only awarded 30 pts with no base coverage, score would be 182.0
    understated_score = (c_full * 30.0) + (std_full * 10.0) - (hours * 3.0)
    assert score_layered != understated_score
    assert understated_score == 182.0

    # 4. Rigorous verification across all 11 evaluated plans
    for plan in opt.evaluated_plans:
        pf_crit = sum(
            1 for aid in plan.fully_protected_asset_ids
            if any(s.asset_id == aid and ("Tier 1" in s.criticality or "Tier 2" in s.criticality) for s in inv.affected_services)
        )
        pm_crit = sum(
            1 for aid in plan.partially_mitigated_asset_ids
            if any(s.asset_id == aid and ("Tier 1" in s.criticality or "Tier 2" in s.criticality) for s in inv.affected_services)
        )
        pf_std = len(plan.fully_protected_asset_ids) - pf_crit
        pm_std = len(plan.partially_mitigated_asset_ids) - pm_crit
        
        # Verify no negative disjoint counts
        assert pf_std >= 0, f"Standard count must be non-negative in {plan.plan_id}"
        assert pm_std >= 0, f"Standard count must be non-negative in {plan.plan_id}"

        # Capacity penalty check
        penalty = 12.0 if plan.plan_id in ["PLAN-MULTI-002", "PLAN-ACT-ACT-007"] else 0.0

        plan_disjoint = round(
            max(0.0, (pf_crit * 40.0) + (pm_crit * 20.0) + (pf_std * 10.0) + (pm_std * 5.0) - (plan.total_estimated_hours * 3.0) - penalty),
            1
        )
        assert plan.composite_benefit_score == plan_disjoint, (
            f"Plan {plan.plan_id} score mismatch: actual={plan.composite_benefit_score} vs disjoint={plan_disjoint}"
        )




