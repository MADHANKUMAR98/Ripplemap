"""Integration test suite for FalkorDB schema, seed idempotency, and scenario topologies.

Tests run directly against the live FalkorDB container instance.
"""

import pytest
from app.db import db_client
from app.seed import seed_database


def test_database_connectivity():
    """Verify that the FalkorDB container is running and healthy."""
    assert db_client.is_healthy() is True
    res = db_client.query("RETURN 1 AS ping")
    assert len(res) == 1
    assert res[0][0] == 1


def test_node_counts_and_domain_labels():
    """Verify total node count and presence of all domain-specific infrastructure labels."""
    total_infra_nodes = db_client.query("MATCH (n:InfrastructureNode) RETURN count(n)")[0][0]
    # Expect 56 infrastructure nodes (5 zones + 51 physical assets)
    assert total_infra_nodes == 56

    label_expectations = {
        "Substation": 6,
        "WaterPump": 10,
        "MobileTower": 6,
        "Hospital": 2,
        "Clinic": 6,
        "EmergencyCenter": 5,
        "Road": 9,
        "BackupGenerator": 7,
        "InfrastructureZone": 5,
    }

    for label, min_count in label_expectations.items():
        actual_count = db_client.query(f"MATCH (n:{label}) RETURN count(n)")[0][0]
        assert actual_count >= min_count, f"Label {label} expected >= {min_count}, got {actual_count}"


def test_required_relationship_types():
    """Verify all required infrastructure and memory relationship types exist in the graph."""
    required_types = [
        "SUPPLIES_POWER_TO",
        "SUPPLIES_WATER_TO",
        "SUPPORTS_COMMUNICATION_FOR",
        "CONNECTS_TO",
        "HAS_BACKUP",
        "DEPENDS_ON",
        "LOCATED_IN",
        "TRIGGERED_BY",
        "AFFECTED",
        "USED_ACTION",
        "TARGETS",
        "SUPPORTED_BY",
    ]

    for rel_type in required_types:
        count = db_client.query(f"MATCH ()-[r:{rel_type}]->() RETURN count(r)")[0][0]
        assert count > 0, f"Relationship type {rel_type} missing from graph"


def test_seed_idempotency():
    """Verify that re-running seed_database does not create duplicate nodes or relationships."""
    initial_nodes = db_client.query("MATCH (n) RETURN count(n)")[0][0]
    initial_rels = db_client.query("MATCH ()-[r]->() RETURN count(r)")[0][0]

    # Re-run seeder without clearing
    seed_database(client=db_client, clear_existing=False)

    post_seed_nodes = db_client.query("MATCH (n) RETURN count(n)")[0][0]
    post_seed_rels = db_client.query("MATCH ()-[r]->() RETURN count(r)")[0][0]

    assert post_seed_nodes == initial_nodes, f"Node count changed from {initial_nodes} to {post_seed_nodes}"
    assert post_seed_rels == initial_rels, f"Relationship count changed from {initial_rels} to {post_seed_rels}"

    # Ensure no duplicate node IDs exist
    duplicates = db_client.query("""
        MATCH (n:InfrastructureNode)
        WITH n.id AS id, count(n) AS c
        WHERE c > 1
        RETURN id, c
    """)
    assert len(duplicates) == 0, f"Found duplicate nodes: {duplicates}"


def test_multi_hop_cascade_scenario():
    """Verify multi-hop dependency path from SUB-001 down to HOSP-001 and EMERG-001."""
    # Path 1: SUB-001 -[SUPPLIES_POWER_TO]-> PUMP-001 -[SUPPLIES_WATER_TO]-> HOSP-001
    water_cascade = db_client.query("""
        MATCH (sub:Substation {id: 'SUB-001'})-[:SUPPLIES_POWER_TO]->(pump:WaterPump {id: 'PUMP-001'})-[:SUPPLIES_WATER_TO]->(hosp:Hospital {id: 'HOSP-001'})
        RETURN sub.id, pump.id, hosp.id
    """)
    assert len(water_cascade) >= 1
    assert water_cascade[0] == ["SUB-001", "PUMP-001", "HOSP-001"]

    # Path 2: SUB-001 -[SUPPLIES_POWER_TO]-> TOWER-001 -[SUPPORTS_COMMUNICATION_FOR]-> HOSP-001
    telemetry_cascade = db_client.query("""
        MATCH (sub:Substation {id: 'SUB-001'})-[:SUPPLIES_POWER_TO]->(tow:MobileTower {id: 'TOWER-001'})-[:SUPPORTS_COMMUNICATION_FOR]->(hosp:Hospital {id: 'HOSP-001'})
        RETURN sub.id, tow.id, hosp.id
    """)
    assert len(telemetry_cascade) >= 1
    assert telemetry_cascade[0] == ["SUB-001", "TOWER-001", "HOSP-001"]

    # Path 3: SUB-001 -[SUPPLIES_POWER_TO]-> TOWER-001 -[SUPPORTS_COMMUNICATION_FOR]-> EMERG-001
    eoc_cascade = db_client.query("""
        MATCH (sub:Substation {id: 'SUB-001'})-[:SUPPLIES_POWER_TO]->(tow:MobileTower {id: 'TOWER-001'})-[:SUPPORTS_COMMUNICATION_FOR]->(eoc:EmergencyCenter {id: 'EMERG-001'})
        RETURN sub.id, tow.id, eoc.id
    """)
    assert len(eoc_cascade) >= 1
    assert eoc_cascade[0] == ["SUB-001", "TOWER-001", "EMERG-001"]


def test_genuine_alternate_supply_routes():
    """Verify genuine alternate supply route exists from SUB-002 to TOWER-001 and alternate road to HOSP-001."""
    # Auxiliary electrical tie-line to TOWER-001
    alt_power = db_client.query("""
        MATCH (sub:Substation {id: 'SUB-002'})-[r:SUPPLIES_POWER_TO]->(tow:MobileTower {id: 'TOWER-001'})
        WHERE r.is_redundant = true AND r.dependency_type = 'auxiliary_tie_line'
        RETURN sub.id, tow.id, r.dependency_type
    """)
    assert len(alt_power) == 1
    assert alt_power[0][0] == "SUB-002"
    assert alt_power[0][1] == "TOWER-001"

    # Alternate emergency road corridor to HOSP-001
    alt_road = db_client.query("""
        MATCH (road:Road {id: 'ROAD-002'})-[r:CONNECTS_TO]->(hosp:Hospital {id: 'HOSP-001'})
        WHERE r.is_redundant = true
        RETURN road.id, hosp.id
    """)
    assert len(alt_road) == 1
    assert alt_road[0][0] == "ROAD-002"


def test_unavailable_and_insufficient_backups():
    """Verify modeled backup generators include one insufficient capacity and one unavailable backup."""
    # 1. Insufficient capacity: GEN-002 connected to PUMP-001
    insufficient = db_client.query("""
        MATCH (pump:WaterPump {id: 'PUMP-001'})-[:HAS_BACKUP]->(gen:BackupGenerator {id: 'GEN-002'})
        RETURN gen.id, gen.status, gen.capacity_rating
    """)
    assert len(insufficient) == 1
    gen_id, status, capacity = insufficient[0]
    assert gen_id == "GEN-002"
    assert status == "DEGRADED"
    assert "INSUFFICIENT" in capacity.upper()

    # 2. Unavailable backup: GEN-005 connected to CLINIC-003
    unavailable = db_client.query("""
        MATCH (clinic:Clinic {id: 'CLINIC-003'})-[:HAS_BACKUP]->(gen:BackupGenerator {id: 'GEN-005'})
        RETURN gen.id, gen.status, gen.buffer_hours
    """)
    assert len(unavailable) == 1
    gen_id, status, buffer_hours = unavailable[0]
    assert gen_id == "GEN-005"
    assert status == "FAILED"
    assert buffer_hours == 0.0


def test_shared_upstream_dependency():
    """Verify SUB-001 acts as a shared upstream dependency across multiple critical services."""
    res = db_client.query("""
        MATCH (sub:Substation {id: 'SUB-001'})-[:SUPPLIES_POWER_TO]->(target:InfrastructureNode)
        RETURN target.id, target.entity_type
    """)
    # SUB-001 powers PUMP-001, PUMP-002, TOWER-001, EMERG-001, ROAD-001, CLINIC-001 (6 distinct targets)
    assert len(res) >= 5
    target_ids = {row[0] for row in res}
    expected_critical_targets = {"PUMP-001", "TOWER-001", "EMERG-001", "ROAD-001"}
    assert expected_critical_targets.issubset(target_ids)


def test_incident_memory_retrieval():
    """Verify historical baseline incident record is persisted with links to affected nodes, actions, and evidence."""
    incident = db_client.query("""
        MATCH (inc:Incident {id: 'INC-2026-001'})-[:TRIGGERED_BY]->(sub:Substation),
              (inc)-[:AFFECTED]->(hosp:Hospital),
              (inc)-[:USED_ACTION]->(act:RecoveryAction)-[:TARGETS]->(tow:MobileTower),
              (inc)-[:SUPPORTED_BY]->(evd:EvidenceRecord)
        RETURN inc.id, sub.id, hosp.id, act.id, tow.id, evd.id
    """)
    assert len(incident) >= 1
    row = incident[0]
    assert row[0] == "INC-2026-001"
    assert row[1] == "SUB-001"
    assert row[2] == "HOSP-001"
    assert row[3] == "ACT-2026-001"
    assert row[4] == "TOWER-001"
    assert row[5] == "EVD-2026-001"
