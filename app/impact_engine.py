"""Deterministic investigation engine for RippleMap.

Traces multi-hop cascading consequences, synthesizes graph path evidence, evaluates alternative routes
and backup generators, and classifies infrastructure impacts with deterministic rigor.
Does not use LLMs to fabricate or extrapolate unverified graph facts.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from app.db import FalkorDBClient, db_client
from app.schema import (
    ImpactClassification,
    EvidencePath,
    AffectedAssetFinding,
    InvestigationResult,
)
from app.graph_queries import (
    validate_node_id,
    get_node_by_id,
    get_direct_dependencies,
    get_downstream_paths,
    get_alternate_supply_paths,
    get_backups_for_node,
    get_shared_upstream_analysis,
    get_historical_incidents_for_node,
)

logger = logging.getLogger(__name__)


def _format_path_summary(node_ids: list[str], rel_types: list[str]) -> str:
    """Formats a concise readable path string like: SUB-001 -[SUPPLIES_POWER_TO]-> PUMP-001 -> HOSP-001."""
    if len(node_ids) == 1:
        return node_ids[0]
    segments = []
    for i in range(len(rel_types)):
        src = node_ids[i]
        rel = rel_types[i]
        segments.append(f"{src} -[{rel}]-> ")
    segments.append(node_ids[-1])
    return "".join(segments)


def _criticality_weight(crit_str: str) -> int:
    """Maps criticality tier strings to sortable numeric weight (higher = more critical)."""
    if "Tier 1" in crit_str:
        return 4
    if "Tier 2" in crit_str:
        return 3
    if "Tier 3" in crit_str:
        return 2
    return 1


def investigate_incident(
    source_id: str,
    client: Optional[FalkorDBClient] = None,
    max_depth: int = 4
) -> InvestigationResult:
    """Performs a deterministic, evidence-grounded cascading failure investigation
    starting from a failed or degraded infrastructure component.
    
    Args:
        source_id: The unique ID of the failed infrastructure node (e.g., 'SUB-001').
        client: Optional FalkorDB client.
        max_depth: Maximum hops for bounded downstream exploration (default: 4).
        
    Returns:
        Structured InvestigationResult containing all affected assets, deduplicated evidence paths,
        impact classifications, alternate routes, backup alerts, and next-step checks.
    """
    clean_id = validate_node_id(source_id)
    db = client or db_client

    # 1. Validate that the component exists in the graph
    source_node = get_node_by_id(clean_id, client=db)
    if not source_node:
        raise ValueError(f"Infrastructure component '{clean_id}' does not exist in Ripple City graph.")

    # 2. Validate component entity type (zones represent geographic boundaries, not active infrastructure)
    if source_node["entity_type"] == "InfrastructureZone":
        raise ValueError(
            f"Component '{clean_id}' is an InfrastructureZone (geographic container), "
            f"not an active infrastructure asset with cascading power/water inputs."
        )

    investigation_timestamp = datetime.now(timezone.utc).isoformat()
    incident_id = f"INC-SIM-{clean_id}-{int(datetime.now(timezone.utc).timestamp())}"

    # 3. Retrieve direct 1-hop dependencies and bounded multi-hop downstream paths
    direct_deps = get_direct_dependencies(clean_id, client=db, direction="downstream")
    raw_paths = get_downstream_paths(clean_id, max_depth=max_depth, client=db)

    # 4. Deduplicate affected services and aggregate supporting evidence paths
    # Key: target_id -> dict of {destination_info, paths: list[EvidencePath]}
    aggregated_targets: dict[str, dict[str, Any]] = {}

    # Process 1-hop direct dependencies
    direct_ids = set()
    for d in direct_deps:
        tid = d["id"]
        direct_ids.add(tid)
        if tid not in aggregated_targets:
            aggregated_targets[tid] = {
                "id": tid,
                "name": d["name"],
                "entity_type": d["entity_type"],
                "criticality": d["criticality"],
                "status": d["status"],
                "zone": d["zone"],
                "paths": [],
                "min_hops": 1,
            }
        ev_path = EvidencePath(
            node_ids=[clean_id, tid],
            relationship_types=[d["rel_type"]],
            hops=1,
            summary=_format_path_summary([clean_id, tid], [d["rel_type"]]),
        )
        aggregated_targets[tid]["paths"].append(ev_path)

    # Process multi-hop downstream paths
    for p in raw_paths:
        dst = p["destination"]
        tid = dst["id"]
        hops = p["hops"]

        if tid not in aggregated_targets:
            aggregated_targets[tid] = {
                "id": tid,
                "name": dst["name"],
                "entity_type": dst["entity_type"],
                "criticality": dst["criticality"],
                "status": dst["status"],
                "zone": dst["zone"],
                "paths": [],
                "min_hops": hops,
            }
        else:
            aggregated_targets[tid]["min_hops"] = min(aggregated_targets[tid]["min_hops"], hops)

        ev_path = EvidencePath(
            node_ids=p["node_path"],
            relationship_types=p["rel_types"],
            hops=hops,
            summary=_format_path_summary(p["node_path"], p["rel_types"]),
        )
        # Avoid duplicate identical paths
        if not any(existing.node_ids == ev_path.node_ids for existing in aggregated_targets[tid]["paths"]):
            aggregated_targets[tid]["paths"].append(ev_path)

    # 5. Evaluate Alternate Routes and Backups for each affected asset
    affected_findings: list[AffectedAssetFinding] = []
    available_mitigations: list[dict[str, Any]] = []
    backup_alerts: list[dict[str, Any]] = []
    recommended_checks: list[str] = []
    assumptions: list[str] = [
        f"Baseline failure source '{clean_id}' is assumed completely non-operational.",
        "Buffer runway assumes zero recharge while upstream supplies remain de-energized.",
        "Simulated impacts represent predicted operational exposure, not verified hardware failure.",
        "No spontaneous unmodeled cross-ties or manual generator transfers exist beyond graph definitions.",
    ]

    all_affected_ids = list(aggregated_targets.keys())
    finding_counter = 1
    for target_id, target_data in aggregated_targets.items():
        min_hops = target_data["min_hops"]
        is_direct = (target_id in direct_ids) or (min_hops == 1)
        crit = target_data["criticality"]
        is_high_criticality = ("Tier 1" in crit or "Tier 2" in crit)

        # Query alternate supplies that bypass clean_id and all cascading de-energized nodes
        alt_supplies = get_alternate_supply_paths(
            target_id, clean_id, client=db, excluded_source_ids=all_affected_ids
        )
        viable_alternates = [a for a in alt_supplies if a.get("is_viable", False)]

        # Query backup systems
        backups = get_backups_for_node(target_id, client=db)
        has_failed_backup = any(b["is_failed"] for b in backups)
        has_insufficient_backup = any(b["is_insufficient"] for b in backups)
        has_ready_backup = any(b["is_ready"] for b in backups)
        has_uncertain_backup = any(b.get("has_uncertain_capacity", False) for b in backups)

        # Collect incoming cascade relationship types and evaluate whether all are covered by alternate supplies
        incoming_cascade_rel_types = set()
        for p in target_data["paths"]:
            if p.relationship_types:
                incoming_cascade_rel_types.add(p.relationship_types[-1])

        # Filter viable alternates to only those that supply the disrupted service domain(s)
        service_matched_alternates = [
            a for a in viable_alternates if a["rel_type"] in incoming_cascade_rel_types
        ]

        mitigated_rel_types = set(a["rel_type"] for a in service_matched_alternates)
        unmitigated_rel_types = incoming_cascade_rel_types - mitigated_rel_types
        is_fully_mitigated = (len(service_matched_alternates) > 0 and len(unmitigated_rel_types) == 0)

        # Record genuine service-matched mitigations
        for a in service_matched_alternates:
            available_mitigations.append({
                "target_id": target_id,
                "target_name": target_data["name"],
                "supplier_id": a["supplier_id"],
                "supplier_name": a["supplier_name"],
                "rel_type": a["rel_type"],
                "dependency_type": a["dependency_type"],
                "is_redundant": a["is_redundant"],
                "estimated_hours": a["estimated_restoration_hours"],
            })

        # 6. Determine Impact Classification
        classification = ImpactClassification.DOWNSTREAM_DEPENDENCY
        target_assumptions: list[str] = []

        if has_uncertain_backup:
            target_assumptions.append(
                f"Generator attached to {target_id} has unmodeled or unverified capacity; flagged as uncertainty."
            )

        if has_failed_backup:
            classification = ImpactClassification.BACKUP_UNAVAILABLE
            target_assumptions.append(f"Backup generator for {target_id} is FAILED or has zero fuel buffer.")
            backup_alerts.append({
                "target_id": target_id,
                "target_name": target_data["name"],
                "issue": "BACKUP_UNAVAILABLE",
                "details": [b for b in backups if b["is_failed"]],
            })
        elif has_insufficient_backup:
            classification = ImpactClassification.BACKUP_CAPACITY_INSUFFICIENT
            target_assumptions.append(f"Backup generator capacity for {target_id} is insufficient for full emergency load.")
            backup_alerts.append({
                "target_id": target_id,
                "target_name": target_data["name"],
                "issue": "INSUFFICIENT_CAPACITY",
                "details": [b for b in backups if b["is_insufficient"]],
            })
        elif is_fully_mitigated:
            classification = ImpactClassification.MITIGATED_BY_ALTERNATIVE
            target_assumptions.append(f"All incoming supply lines have verified alternate bypass routes.")
        elif is_high_criticality:
            classification = ImpactClassification.POTENTIAL_SERVICE_IMPACT
            if service_matched_alternates:
                target_assumptions.append(
                    f"Partial mitigation present ({', '.join(mitigated_rel_types)}), "
                    f"but unmitigated inputs remain ({', '.join(unmitigated_rel_types)})."
                )
        elif is_direct:
            classification = ImpactClassification.DIRECT_DEPENDENCY

        # Formulate explicit simulated outcome statement distinguishing model from confirmed reality
        if classification == ImpactClassification.MITIGATED_BY_ALTERNATIVE:
            simulated_outcome = (
                f"Predicted primary supply loss from {clean_id}. "
                f"MITIGATED: Genuine alternate supply available from {service_matched_alternates[0]['supplier_name']} "
                f"via {service_matched_alternates[0]['dependency_type']} (estimated switchover: {service_matched_alternates[0]['estimated_restoration_hours']}h)."
            )
        elif classification == ImpactClassification.BACKUP_CAPACITY_INSUFFICIENT:
            simulated_outcome = (
                f"Predicted input loss from {clean_id}. Attached backup generator operates with INSUFFICIENT capacity "
                f"under peak load. Service will operate in degraded state."
            )
        elif classification == ImpactClassification.BACKUP_UNAVAILABLE:
            simulated_outcome = (
                f"Predicted input loss from {clean_id}. Emergency backup is UNAVAILABLE (failed/exhausted runway). "
                f"Complete outage anticipated once local buffer expires."
            )
        elif classification == ImpactClassification.POTENTIAL_SERVICE_IMPACT and service_matched_alternates:
            simulated_outcome = (
                f"Predicted high-criticality service exposure. Partial mitigation available via {service_matched_alternates[0]['supplier_name']} "
                f"({service_matched_alternates[0]['rel_type']}), however vital dependency inputs ({', '.join(unmitigated_rel_types)}) remain completely severed."
            )
        elif is_high_criticality:
            simulated_outcome = (
                f"Predicted loss of critical feed from {clean_id} across {min_hops} hop(s). "
                f"Life safety or essential service exposed. Real-time operational state is currently {target_data['status']}."
            )
        else:
            simulated_outcome = (
                f"Predicted supply interruption across {min_hops} hop(s). "
                f"Operational state remains {target_data['status']} pending onsite confirmation."
            )

        finding = AffectedAssetFinding(
            finding_id=f"FIND-{finding_counter:03d}",
            asset_id=target_id,
            asset_name=target_data["name"],
            entity_type=target_data["entity_type"],
            criticality=target_data["criticality"],
            status=target_data["status"],
            classification=classification,
            direct_distance=min_hops,
            evidence_paths=target_data["paths"],
            alternate_supply_available=len(service_matched_alternates) > 0,
            alternate_supply_details=service_matched_alternates,
            backup_available=len(backups) > 0,
            backup_details=backups,
            simulated_outcome=simulated_outcome,
            assumptions=target_assumptions,
        )
        affected_findings.append(finding)
        finding_counter += 1

    # 7. Deterministic Ranking
    # Primary: Criticality tier (Tier 1 > Tier 2 > Tier 3 > Tier 4)
    # Secondary: Unmitigated vs Mitigated (unmitigated prioritized)
    # Tertiary: Direct distance (1-hop before 2-hop)
    # Quaternary: Alphabetical asset ID
    def _sort_key(f: AffectedAssetFinding):
        is_mitigated = 1 if f.classification == ImpactClassification.MITIGATED_BY_ALTERNATIVE else 0
        crit_weight = _criticality_weight(f.criticality)
        return (-crit_weight, is_mitigated, f.direct_distance, f.asset_id)

    affected_findings.sort(key=_sort_key)

    # 8. Compute Counts and Formulate Next Checks
    direct_count = sum(1 for f in affected_findings if f.direct_distance == 1)
    downstream_count = sum(1 for f in affected_findings if f.direct_distance > 1)
    critical_count = sum(1 for f in affected_findings if "Tier 1" in f.criticality or "Tier 2" in f.criticality)

    # Generate evidence-grounded next checks
    if available_mitigations:
        m = available_mitigations[0]
        recommended_checks.append(
            f"Energize alternate supply route: Close switchgear from {m['supplier_id']} ({m['supplier_name']}) "
            f"to {m['target_id']} ({m['target_name']}) to restore service within {m['estimated_hours']} hour(s)."
        )

    for b in backup_alerts:
        if b["issue"] == "INSUFFICIENT_CAPACITY":
            recommended_checks.append(
                f"Dispatch mobile generator trailer to supplement {b['target_id']} ({b['target_name']}) "
                f"before station buffers exhaust."
            )
        elif b["issue"] == "BACKUP_UNAVAILABLE":
            recommended_checks.append(
                f"Dispatch emergency repair crew to inspect {b['target_id']} ({b['target_name']}) "
                f"backup generator starter mechanism immediately."
            )

    # Check shared upstream dependency analysis
    spof_analysis = get_shared_upstream_analysis(clean_id, client=db)
    if spof_analysis.get("is_shared_upstream_spof", False):
        recommended_checks.append(
            f"PRIORITY ALERT: {clean_id} is a confirmed shared upstream Single Point of Failure (SPOF) "
            f"feeding {spof_analysis['sector_count']} sectors ({', '.join(spof_analysis['sectors'])}) "
            f"and {spof_analysis['critical_services_count']} Tier 1/2 critical services. Mobilize primary grid restoration team."
        )

    # Incident memory retrieval
    past_incidents = get_historical_incidents_for_node(clean_id, client=db)
    if past_incidents:
        past = past_incidents[0]
        recommended_checks.append(
            f"Reference historical incident memory: Past incident '{past['title']}' ({past['incident_id']}) "
            f"successfully used action '{past.get('recovery_action_name', 'N/A')}'."
        )

    # Summary synthesis
    summary = (
        f"Investigation of {source_node['name']} ({clean_id}) identified {len(affected_findings)} affected components "
        f"({direct_count} direct, {downstream_count} downstream), including {critical_count} critical services. "
        f"{len(available_mitigations)} alternate mitigation(s) and {len(backup_alerts)} backup constraint alert(s) discovered."
    )

    return InvestigationResult(
        incident_id=incident_id,
        source_node_id=clean_id,
        source_node_name=source_node["name"],
        source_entity_type=source_node["entity_type"],
        source_status=source_node["status"],
        investigation_status="COMPLETED",
        summary=summary,
        total_affected_count=len(affected_findings),
        direct_dependency_count=direct_count,
        downstream_dependency_count=downstream_count,
        critical_services_count=critical_count,
        affected_services=affected_findings,
        available_mitigations=available_mitigations,
        backup_alerts=backup_alerts,
        recommended_checks=recommended_checks,
        assumptions=assumptions,
        timestamp=investigation_timestamp,
    )
