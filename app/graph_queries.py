"""FalkorDB Cypher query layer for RippleMap.

Provides clean, safe, parameterized query functions for node inspection, bounded multi-hop traversals,
alternative supply path detection, backup evaluation, and incident memory retrieval.
"""

import re
import logging
from typing import Any, Optional
from app.db import FalkorDBClient, db_client

logger = logging.getLogger(__name__)

# Alphanumeric with hyphens and underscores for safe node ID validation
NODE_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]+$")


def validate_node_id(node_id: str) -> str:
    """Validates that a node ID conforms to expected safe pattern to prevent Cypher injection."""
    if not isinstance(node_id, str) or not node_id.strip():
        raise ValueError("Node ID must be a non-empty string.")
    cleaned = node_id.strip()
    if not NODE_ID_REGEX.match(cleaned):
        raise ValueError(f"Invalid node ID format '{cleaned}'. Must contain only letters, numbers, hyphens, and underscores.")
    return cleaned


def get_node_by_id(node_id: str, client: Optional[FalkorDBClient] = None) -> Optional[dict[str, Any]]:
    """Retrieves an infrastructure node by ID along with its operational status and properties.
    
    Returns None if the node is not found in the database.
    """
    clean_id = validate_node_id(node_id)
    db = client or db_client

    cypher = """
    MATCH (n:InfrastructureNode {id: $node_id})
    RETURN n.id, n.name, n.entity_type, n.criticality, n.status, n.zone,
           n.latitude, n.longitude, n.buffer_hours, n.capacity_rating, n.notes, labels(n)
    """
    try:
        results = db.query(cypher, {"node_id": clean_id})
        if not results:
            return None
        row = results[0]
        return {
            "id": row[0],
            "name": row[1],
            "entity_type": row[2],
            "criticality": row[3],
            "status": row[4],
            "zone": row[5],
            "latitude": float(row[6]) if row[6] is not None else 0.0,
            "longitude": float(row[7]) if row[7] is not None else 0.0,
            "buffer_hours": float(row[8]) if row[8] is not None else 0.0,
            "capacity_rating": row[9] or "",
            "notes": row[10] or "",
            "labels": row[11] if len(row) > 11 else ["InfrastructureNode"],
        }
    except Exception as e:
        logger.error(f"Error fetching node by ID '{clean_id}': {e}")
        raise RuntimeError(f"Database error querying node '{clean_id}': {e}") from e


def get_direct_dependencies(
    node_id: str,
    client: Optional[FalkorDBClient] = None,
    direction: str = "downstream"
) -> list[dict[str, Any]]:
    """Retrieves 1-hop direct dependencies for a given node.
    
    direction='downstream': finds nodes supplied or supported by this node: (node)-[r]->(target)
    direction='upstream': finds nodes that supply or support this node: (source)-[r]->(node)
    Excludes LOCATED_IN and HAS_BACKUP relationships.
    """
    clean_id = validate_node_id(node_id)
    db = client or db_client

    if direction == "downstream":
        cypher = """
        MATCH (src:InfrastructureNode {id: $node_id})-[r]->(dst:InfrastructureNode)
        WHERE type(r) <> 'LOCATED_IN' AND type(r) <> 'HAS_BACKUP' AND type(r) <> 'DEPENDS_ON'
        RETURN dst.id, dst.name, dst.entity_type, dst.criticality, dst.status, dst.zone,
               type(r) AS rel_type, r.dependency_type, r.confidence, r.is_redundant,
               r.estimated_restoration_hours, r.description
        """
    elif direction == "upstream":
        cypher = """
        MATCH (src:InfrastructureNode)-[r]->(dst:InfrastructureNode {id: $node_id})
        WHERE type(r) <> 'LOCATED_IN' AND type(r) <> 'HAS_BACKUP' AND type(r) <> 'DEPENDS_ON'
        RETURN src.id, src.name, src.entity_type, src.criticality, src.status, src.zone,
               type(r) AS rel_type, r.dependency_type, r.confidence, r.is_redundant,
               r.estimated_restoration_hours, r.description
        """
    else:
        raise ValueError(f"Invalid direction '{direction}'. Must be 'downstream' or 'upstream'.")

    try:
        results = db.query(cypher, {"node_id": clean_id})
        dependencies = []
        for row in results:
            dependencies.append({
                "id": row[0],
                "name": row[1],
                "entity_type": row[2],
                "criticality": row[3],
                "status": row[4],
                "zone": row[5],
                "rel_type": row[6],
                "dependency_type": row[7] or "",
                "confidence": float(row[8]) if row[8] is not None else 1.0,
                "is_redundant": bool(row[9]) if row[9] is not None else False,
                "estimated_restoration_hours": float(row[10]) if row[10] is not None else 0.0,
                "description": row[11] or "",
            })
        return dependencies
    except Exception as e:
        logger.error(f"Error querying direct dependencies for '{clean_id}': {e}")
        raise RuntimeError(f"Database error querying direct dependencies for '{clean_id}': {e}") from e


def get_downstream_paths(
    source_id: str,
    max_depth: int = 4,
    client: Optional[FalkorDBClient] = None
) -> list[dict[str, Any]]:
    """Traverses downstream supply and communication relationships using a bounded Cypher path query.
    
    Guarantees cycle prevention and bounded exploration (depth 1 to max_depth).
    Excludes zone containment (LOCATED_IN) and backup links (HAS_BACKUP).
    """
    clean_id = validate_node_id(source_id)
    safe_depth = max(1, min(int(max_depth), 6))  # Strict bounds between 1 and 6
    db = client or db_client

    # Bounded Cypher traversal across physical supply and access edges
    cypher = f"""
    MATCH p = (src:InfrastructureNode {{id: $source_id}})-[:SUPPLIES_POWER_TO|SUPPLIES_WATER_TO|SUPPORTS_COMMUNICATION_FOR|CONNECTS_TO*1..{safe_depth}]->(dst:InfrastructureNode)
    WHERE src <> dst
    RETURN [n in nodes(p) | n.id] AS node_path,
           [n in nodes(p) | n.name] AS name_path,
           [r in relationships(p) | type(r)] AS rel_types,
           length(p) AS hops,
           dst.id AS dest_id, dst.name AS dest_name, dst.entity_type AS dest_type,
           dst.criticality AS dest_criticality, dst.status AS dest_status, dst.zone AS dest_zone
    """
    try:
        results = db.query(cypher, {"source_id": clean_id})
        paths = []
        for row in results:
            paths.append({
                "node_path": row[0],
                "name_path": row[1],
                "rel_types": row[2],
                "hops": int(row[3]),
                "destination": {
                    "id": row[4],
                    "name": row[5],
                    "entity_type": row[6],
                    "criticality": row[7],
                    "status": row[8],
                    "zone": row[9],
                }
            })
        return paths
    except Exception as e:
        logger.error(f"Error traversing downstream paths for '{clean_id}': {e}")
        raise RuntimeError(f"Database error traversing downstream paths for '{clean_id}': {e}") from e


def get_alternate_supply_paths(
    target_id: str,
    failed_source_id: str,
    client: Optional[FalkorDBClient] = None,
    excluded_source_ids: Optional[list[str]] = None
) -> list[dict[str, Any]]:
    """Identifies alternative supply feeds or access routes leading to target_id
    that do NOT originate from failed_source_id or any other de-energized/affected nodes.
    
    Checks both primary feeds from alternate sources and redundant/auxiliary tie-lines.
    """
    clean_target = validate_node_id(target_id)
    clean_failed = validate_node_id(failed_source_id)
    db = client or db_client

    exclusions = list(set([clean_failed] + (excluded_source_ids or [])))

    cypher = """
    MATCH (alt:InfrastructureNode)-[r:SUPPLIES_POWER_TO|SUPPLIES_WATER_TO|SUPPORTS_COMMUNICATION_FOR|CONNECTS_TO]->(dst:InfrastructureNode {id: $target_id})
    WHERE NOT alt.id IN $exclusions
    RETURN alt.id, alt.name, alt.entity_type, alt.status, type(r) AS rel_type,
           r.dependency_type, r.is_redundant, r.estimated_restoration_hours, r.description
    """
    try:
        results = db.query(cypher, {"target_id": clean_target, "exclusions": exclusions})
        alternatives = []
        for row in results:
            alternatives.append({
                "supplier_id": row[0],
                "supplier_name": row[1],
                "supplier_type": row[2],
                "supplier_status": row[3],
                "rel_type": row[4],
                "dependency_type": row[5] or "",
                "is_redundant": bool(row[6]) if row[6] is not None else False,
                "estimated_restoration_hours": float(row[7]) if row[7] is not None else 0.0,
                "description": row[8] or "",
                "is_viable": row[3] == "OPERATIONAL",
            })
        return alternatives
    except Exception as e:
        logger.error(f"Error querying alternate supplies for '{clean_target}': {e}")
        raise RuntimeError(f"Database error querying alternate supplies for '{clean_target}': {e}") from e


def get_backups_for_node(
    node_id: str,
    client: Optional[FalkorDBClient] = None
) -> list[dict[str, Any]]:
    """Retrieves all backup generators attached to a node via HAS_BACKUP,
    evaluating operational readiness and capacity sufficiency.
    """
    clean_id = validate_node_id(node_id)
    db = client or db_client

    cypher = """
    MATCH (n:InfrastructureNode {id: $node_id})-[r:HAS_BACKUP]->(gen:BackupGenerator)
    RETURN gen.id, gen.name, gen.status, gen.capacity_rating, gen.buffer_hours,
           gen.notes, r.dependency_type, r.confidence, r.is_redundant
    """
    try:
        results = db.query(cypher, {"node_id": clean_id})
        backups = []
        for row in results:
            gen_id = row[0]
            gen_name = row[1]
            gen_status = row[2]
            capacity_rating = row[3] or ""
            buffer_hours = float(row[4]) if row[4] is not None else 0.0
            notes = row[5] or ""
            dependency_type = row[6] or ""
            confidence = float(row[7]) if row[7] is not None else 1.0

            # Evaluate backup constraints deterministically based on graph properties
            is_failed = (gen_status == "FAILED" or buffer_hours <= 0.0)
            has_uncertain_capacity = (not capacity_rating or capacity_rating.strip() == "")
            is_insufficient = (
                "INSUFFICIENT" in capacity_rating.upper()
                or "INSUFFICIENT" in notes.upper()
                or gen_status == "DEGRADED"
            )
            is_ready = (
                gen_status == "OPERATIONAL"
                and buffer_hours > 0.0
                and not is_insufficient
                and not has_uncertain_capacity
            )

            backups.append({
                "generator_id": gen_id,
                "generator_name": gen_name,
                "status": gen_status,
                "capacity_rating": capacity_rating,
                "buffer_hours": buffer_hours,
                "notes": notes,
                "dependency_type": dependency_type,
                "confidence": confidence,
                "is_ready": is_ready,
                "is_failed": is_failed,
                "is_insufficient": is_insufficient,
                "has_uncertain_capacity": has_uncertain_capacity,
            })
        return backups
    except Exception as e:
        logger.error(f"Error querying backups for '{clean_id}': {e}")
        raise RuntimeError(f"Database error querying backups for '{clean_id}': {e}") from e


def get_shared_upstream_analysis(
    source_id: str,
    client: Optional[FalkorDBClient] = None
) -> dict[str, Any]:
    """Analyzes whether a component is a critical shared upstream dependency
    by evaluating the diversity of sectors and criticality tiers of its downstream dependencies.
    """
    direct_deps = get_direct_dependencies(source_id, client=client, direction="downstream")
    downstream_paths = get_downstream_paths(source_id, max_depth=3, client=client)

    distinct_sectors = set()
    critical_services = set()
    for d in direct_deps:
        distinct_sectors.add(d["entity_type"])
        if "Tier 1" in d["criticality"] or "Tier 2" in d["criticality"]:
            critical_services.add(d["id"])

    for p in downstream_paths:
        dst = p["destination"]
        distinct_sectors.add(dst["entity_type"])
        if "Tier 1" in dst["criticality"] or "Tier 2" in dst["criticality"]:
            critical_services.add(dst["id"])

    is_shared_spof = len(distinct_sectors) >= 3 and len(critical_services) >= 3

    return {
        "source_id": source_id,
        "is_shared_upstream_spof": is_shared_spof,
        "sector_count": len(distinct_sectors),
        "sectors": sorted(list(distinct_sectors)),
        "critical_services_count": len(critical_services),
        "critical_services": sorted(list(critical_services)),
    }


def get_historical_incidents_for_node(
    node_id: str,
    client: Optional[FalkorDBClient] = None
) -> list[dict[str, Any]]:
    """Retrieves persisted incident memory records connected to this node
    via TRIGGERED_BY (root cause) or AFFECTED (impacted asset).
    """
    clean_id = validate_node_id(node_id)
    db = client or db_client

    cypher = """
    MATCH (inc:Incident)-[r:TRIGGERED_BY|AFFECTED]->(n:InfrastructureNode {id: $node_id})
    OPTIONAL MATCH (inc)-[:USED_ACTION]->(act:RecoveryAction)
    OPTIONAL MATCH (inc)-[:SUPPORTED_BY]->(evd:EvidenceRecord)
    RETURN inc.id, inc.title, inc.timestamp, inc.root_cause_type, inc.severity, inc.simulated,
           type(r) AS involvement, act.id, act.action_name, act.expected_benefit, evd.path_summary
    """
    try:
        results = db.query(cypher, {"node_id": clean_id})
        incidents = []
        for row in results:
            incidents.append({
                "incident_id": row[0],
                "title": row[1],
                "timestamp": row[2],
                "root_cause_type": row[3],
                "severity": row[4],
                "simulated": bool(row[5]) if row[5] is not None else True,
                "involvement": row[6],
                "recovery_action_id": row[7],
                "recovery_action_name": row[8],
                "expected_benefit": row[9],
                "evidence_path_summary": row[10],
            })
        return incidents
    except Exception as e:
        logger.error(f"Error querying historical incidents for '{clean_id}': {e}")
        raise RuntimeError(f"Database error querying historical incidents for '{clean_id}': {e}") from e


def get_selectable_infrastructure_nodes(
    client: Optional[FalkorDBClient] = None
) -> list[dict[str, Any]]:
    """Retrieves all selectable physical infrastructure assets for dashboard source selection.
    
    Returns list of dicts with: id, name, entity_type, criticality, status, zone.
    Guarantees deterministic sorting.
    """
    db = client or db_client
    cypher = """
    MATCH (n:InfrastructureNode)
    WHERE n.entity_type IN ['Substation', 'WaterPump', 'Hospital', 'MobileTower', 'Clinic', 'EmergencyCenter', 'Road']
    RETURN n.id, n.name, n.entity_type, n.criticality, n.status, n.zone
    ORDER BY n.id ASC
    """
    try:
        results = db.query(cypher)
        nodes = []
        for row in results:
            nodes.append({
                "id": row[0],
                "name": row[1],
                "entity_type": row[2],
                "criticality": row[3],
                "status": row[4],
                "zone": row[5] or "Ripple City",
            })
        return nodes
    except Exception as e:
        logger.error(f"Error querying selectable infrastructure nodes: {e}")
        return []

