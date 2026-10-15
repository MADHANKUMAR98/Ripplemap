"""Integration test suite for RippleMap's deterministic core investigation engine.

Verifies graph traversal, multi-hop evidence paths, deduplication, impact classification,
alternate supply detection, backup generator constraints, and error handling against live FalkorDB.
"""

import pytest
from app.db import db_client
from app.schema import ImpactClassification, InvestigationResult
from app.graph_queries import (
    validate_node_id,
    get_node_by_id,
    get_direct_dependencies,
    get_downstream_paths,
    get_alternate_supply_paths,
    get_backups_for_node,
    get_shared_upstream_analysis,
)
from app.impact_engine import investigate_incident


def test_unknown_incident_source():
    """Verify that investigating a non-existent component raises ValueError."""
    with pytest.raises(ValueError, match="does not exist in Ripple City graph"):
        investigate_incident("NON-EXISTENT-999")


def test_invalid_source_id_format():
    """Verify that malformed or injection-like node IDs are caught by validation."""
    with pytest.raises(ValueError, match="Invalid node ID format"):
        investigate_incident("SUB-001; DROP ALL;")


def test_invalid_source_type_zone():
    """Verify that investigating an InfrastructureZone raises ValueError."""
    with pytest.raises(ValueError, match="is an InfrastructureZone"):
        investigate_incident("ZONE-DTN")


def test_direct_dependency_discovery():
    """Verify 1-hop direct dependencies for SUB-001 include water, communications, and roads."""
    direct = get_direct_dependencies("SUB-001", direction="downstream")
    target_ids = {d["id"] for d in direct}
    assert "PUMP-001" in target_ids
    assert "TOWER-001" in target_ids
    assert "EMERG-001" in target_ids
    assert "ROAD-001" in target_ids
    assert "CLINIC-001" in target_ids

    # Upstream direction test: PUMP-001 should have SUB-001 as upstream power supplier
    upstream = get_direct_dependencies("PUMP-001", direction="upstream")
    upstream_ids = {u["id"] for u in upstream}
    assert "SUB-001" in upstream_ids


def test_multi_hop_path_evidence_and_deduplication():
    """Verify multi-hop path discovery and deduplication for HOSP-001 from SUB-001."""
    res = investigate_incident("SUB-001")
    assert isinstance(res, InvestigationResult)
    assert res.investigation_status == "COMPLETED"

    # Find HOSP-001 finding
    hosp_finding = next((f for f in res.affected_services if f.asset_id == "HOSP-001"), None)
    assert hosp_finding is not None, "HOSP-001 must be discovered in SUB-001 cascade"

    # HOSP-001 must be counted exactly once in affected services
    hosp_occurrences = [f for f in res.affected_services if f.asset_id == "HOSP-001"]
    assert len(hosp_occurrences) == 1, "Affected services must be deduplicated"

    # HOSP-001 must have multiple distinct supporting evidence paths
    assert len(hosp_finding.evidence_paths) >= 3, "HOSP-001 must record multiple distinct incoming evidence paths"
    summaries = [p.summary for p in hosp_finding.evidence_paths]
    
    # Path through Water Pumping Station
    assert any("PUMP-001" in s and "SUPPLIES_WATER_TO" in s for s in summaries)
    # Path through Mobile Tower
    assert any("TOWER-001" in s and "SUPPORTS_COMMUNICATION_FOR" in s for s in summaries)
    # Path through Highway Corridor
    assert any("ROAD-001" in s and "CONNECTS_TO" in s for s in summaries)


def test_bounded_traversal_behavior():
    """Verify that bounded traversal respects depth limits and avoids cycle loops."""
    # Test with depth 1: should only return 1-hop targets
    paths_depth_1 = get_downstream_paths("SUB-001", max_depth=1)
    for p in paths_depth_1:
        assert p["hops"] == 1

    # Test with depth 2: max hops should be 2
    paths_depth_2 = get_downstream_paths("SUB-001", max_depth=2)
    for p in paths_depth_2:
        assert p["hops"] <= 2


def test_shared_upstream_dependency_detection():
    """Verify that SUB-001 is classified as a shared upstream SPOF feeding >= 4 distinct sectors."""
    spof = get_shared_upstream_analysis("SUB-001")
    assert spof["is_shared_upstream_spof"] is True
    assert spof["sector_count"] >= 4
    assert spof["critical_services_count"] >= 4
    # Expected sectors: Water, MobileTower, Hospital/Clinic, EmergencyCenter, Road
    sectors = set(spof["sectors"])
    assert "WaterPump" in sectors
    assert "MobileTower" in sectors
    assert "EmergencyCenter" in sectors


def test_alternate_route_retrieval_and_mitigation():
    """Verify TOWER-001 has genuine alternate supply route from SUB-002 and is classified MITIGATED."""
    res = investigate_incident("SUB-001")
    tower_finding = next((f for f in res.affected_services if f.asset_id == "TOWER-001"), None)
    assert tower_finding is not None
    assert tower_finding.alternate_supply_available is True
    assert tower_finding.classification == ImpactClassification.MITIGATED_BY_ALTERNATIVE
    assert len(tower_finding.alternate_supply_details) >= 1
    alt = tower_finding.alternate_supply_details[0]
    assert alt["supplier_id"] == "SUB-002"
    assert alt["dependency_type"] == "auxiliary_tie_line"
    assert alt["is_redundant"] is True


def test_insufficient_backup_capacity_detection():
    """Verify PUMP-001 backup GEN-002 is identified as having insufficient capacity."""
    res = investigate_incident("SUB-001")
    pump_finding = next((f for f in res.affected_services if f.asset_id == "PUMP-001"), None)
    assert pump_finding is not None
    assert pump_finding.classification == ImpactClassification.BACKUP_CAPACITY_INSUFFICIENT
    assert pump_finding.backup_available is True
    assert len(pump_finding.backup_details) >= 1
    backup = pump_finding.backup_details[0]
    assert backup["generator_id"] == "GEN-002"
    assert backup["is_insufficient"] is True
    assert "INSUFFICIENT" in backup["capacity_rating"].upper()


def test_unavailable_backup_detection():
    """Verify CLINIC-003 backup GEN-005 is identified as FAILED/UNAVAILABLE in SUB-003 cascade."""
    res = investigate_incident("SUB-003")
    clinic_finding = next((f for f in res.affected_services if f.asset_id == "CLINIC-003"), None)
    assert clinic_finding is not None
    assert clinic_finding.classification == ImpactClassification.BACKUP_UNAVAILABLE
    assert clinic_finding.backup_available is True
    backup = clinic_finding.backup_details[0]
    assert backup["generator_id"] == "GEN-005"
    assert backup["is_failed"] is True
    assert backup["status"] == "FAILED"
    assert backup["buffer_hours"] == 0.0


def test_deterministic_ranking_and_response_structure():
    """Verify that results are deterministically ordered by criticality and unmitigated status."""
    res = investigate_incident("SUB-001")
    assert res.source_node_id == "SUB-001"
    assert res.source_node_name == "Metro Central Substation"
    assert res.total_affected_count == len(res.affected_services)
    assert res.direct_dependency_count + res.downstream_dependency_count == res.total_affected_count

    # Tier 1 services must precede Tier 3 services in the ranking
    tier_1_seen = False
    for f in res.affected_services:
        if "Tier 1" in f.criticality:
            tier_1_seen = True
        elif "Tier 3" in f.criticality:
            assert tier_1_seen, "Tier 1 critical services must appear before Tier 3 services in ranking"

    # Verify structured attributes exist and are populated
    assert len(res.recommended_checks) >= 2
    assert len(res.assumptions) >= 3
    assert res.timestamp is not None


def test_service_matched_mitigation_audit():
    """Audit verification: ensure that unrelated incoming feeds (e.g. water to an unpowered pump)
    are NOT falsely classified as mitigations for electrical failure."""
    res = investigate_incident("SUB-001")
    pump_finding = next((f for f in res.affected_services if f.asset_id == "PUMP-001"), None)
    assert pump_finding is not None

    # PUMP-001 lost SUPPLIES_POWER_TO. PUMP-009 supplies SUPPLIES_WATER_TO.
    # PUMP-009 must NOT be listed as an alternate supply for PUMP-001's electrical loss.
    for alt in pump_finding.alternate_supply_details:
        assert alt["rel_type"] == "SUPPLIES_POWER_TO", "Alternate supply must match disrupted relationship type"

    # All entries in available_mitigations must match the disrupted service domain
    for m in res.available_mitigations:
        target_finding = next((f for f in res.affected_services if f.asset_id == m["target_id"]), None)
        assert target_finding is not None
        incoming_cascade_rel_types = {p.relationship_types[-1] for p in target_finding.evidence_paths if p.relationship_types}
        assert m["rel_type"] in incoming_cascade_rel_types, f"Mitigation {m['rel_type']} must be in disrupted types {incoming_cascade_rel_types}"


def test_partial_mitigation_preserves_potential_service_impact():
    """Audit verification: HOSP-001 has alternate road corridor (ROAD-002),
    but water and telemetry are unmitigated, so its classification must remain POTENTIAL_SERVICE_IMPACT."""
    res = investigate_incident("SUB-001")
    hosp_finding = next((f for f in res.affected_services if f.asset_id == "HOSP-001"), None)
    assert hosp_finding is not None
    assert hosp_finding.classification == ImpactClassification.POTENTIAL_SERVICE_IMPACT
    assert hosp_finding.alternate_supply_available is True  # ROAD-002 is available
    assert any(a["supplier_id"] == "ROAD-002" for a in hosp_finding.alternate_supply_details)
    assert "vital dependency inputs" in hosp_finding.simulated_outcome


def test_backup_capacity_exact_calculation():
    """Audit verification: Verify GEN-002's 1.2 MW against PUMP-001's 3.0 MW requirement (40%)."""
    pump_node = get_node_by_id("PUMP-001")
    backups = get_backups_for_node("PUMP-001")
    assert pump_node is not None
    assert len(backups) == 1
    gen = backups[0]
    assert gen["generator_id"] == "GEN-002"
    assert "3.0 MW" in pump_node["capacity_rating"]
    assert "1.2 MW" in gen["capacity_rating"]
    assert "40%" in gen["notes"]
    assert gen["is_insufficient"] is True

