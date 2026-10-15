"""FalkorDB Incident Memory management for RippleMap.

Provides grounded historical incident retrieval with explicit relevance explanations,
outcome classification (distinguishing observed field outcomes from proposed or simulated actions),
and safe, idempotent memory persistence.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from app.db import FalkorDBClient, db_client
from app.graph_queries import validate_node_id
from app.schema import (
    OutcomeType,
    HistoricalIncidentMatch,
    InvestigationResult,
    ScoreBreakdown,
    RecoveryPlan,
)

logger = logging.getLogger(__name__)


def classify_action_outcome(
    status: Optional[str],
    notes: Optional[str] = None,
    is_simulated: bool = False,
) -> tuple[OutcomeType, str]:
    """Distinguishes observed historical outcomes from proposed or simulated actions.
    
    Returns:
        tuple[OutcomeType, str]: (OutcomeType enum, human-readable outcome explanation)
    """
    clean_status = (status or "").upper().strip()
    notes_lower = (notes or "").lower()

    if is_simulated or clean_status in ("SIMULATED", "SHADOW_SIMULATED") or "simulated" in notes_lower or "simulation" in notes_lower:
        return (
            OutcomeType.SIMULATED_OUTCOME,
            "Simulated contingency outcome derived in-memory or benchmark scenario; not a confirmed real-world recovery.",
        )
    if clean_status == "EXECUTED_SUCCESSFUL":
        return (
            OutcomeType.CONFIRMED_SUCCESSFUL,
            "Historical field action confirmed executed with verified operational recovery.",
        )
    if clean_status == "EXECUTED_FAILED":
        return (
            OutcomeType.CONFIRMED_FAILED,
            "Historical field action confirmed executed but failed to achieve operational recovery.",
        )
    if clean_status.startswith("EXECUTED") or clean_status in ("COMPLETED", "IN_PROGRESS"):
        return (
            OutcomeType.RECORDED_ACTION_TAKEN,
            f"Historical field action recorded with execution status '{clean_status}'; outcome verification pending.",
        )
    if clean_status in ("PROPOSED", "RECOMMENDED", "PLANNED"):
        return (
            OutcomeType.PROPOSED_ACTION,
            "Action proposed or recommended in prior recovery plan; no confirmed field execution or verified outcome.",
        )

    return (
        OutcomeType.MISSING_OUTCOME_DATA,
        "No historical execution or outcome data recorded for this action (outcome unrecorded in incident history).",
    )


def query_incident_memory(
    source_id: str,
    affected_asset_ids: Optional[list[str]] = None,
    client: Optional[FalkorDBClient] = None,
) -> list[HistoricalIncidentMatch]:
    """Retrieves relevant historical incidents and prior recovery actions from FalkorDB.
    
    Matches incidents by:
    1. Same failure source component (TRIGGERED_BY)
    2. Overlapping affected critical services (AFFECTED)
    3. Shared dependency cascade paths (SUPPORTED_BY)
    
    Returns structured matches with explicit relevance explanations and verified outcome types.
    """
    clean_id = validate_node_id(source_id)
    db = client or db_client
    affected_ids = affected_asset_ids or []

    # Map to aggregate matches by (incident_id, action_id)
    aggregated_matches: dict[str, dict[str, Any]] = {}

    # 1. Query: Same failure source component (TRIGGERED_BY)
    cypher_source = """
    MATCH (inc:Incident)-[:TRIGGERED_BY]->(src:InfrastructureNode {id: $source_id})
    OPTIONAL MATCH (inc)-[:AFFECTED]->(aff:InfrastructureNode)
    OPTIONAL MATCH (inc)-[:USED_ACTION]->(act:RecoveryAction)
    OPTIONAL MATCH (inc)-[:SUPPORTED_BY]->(evd:EvidenceRecord)
    RETURN inc.id, inc.title, inc.timestamp, inc.failure_source, inc.severity, inc.simulated, inc.notes,
           collect(DISTINCT aff.id) AS affected_ids,
           act.id, act.action_name, act.action_type, act.status, act.notes,
           evd.path_summary
    """
    try:
        results = db.query(cypher_source, {"source_id": clean_id})
        for row in results:
            inc_id = row[0]
            if not inc_id:
                continue
            act_id = row[8]
            key = f"{inc_id}::{act_id or 'NO_ACT'}"
            aff_ids = row[7] or []

            relevance = f"Direct root cause match: Prior incident '{row[1]}' was triggered by failure of {clean_id}."
            if key not in aggregated_matches:
                aggregated_matches[key] = {
                    "incident_id": inc_id,
                    "title": row[1] or "",
                    "timestamp": row[2] or "",
                    "failure_source": row[3] or clean_id,
                    "severity": row[4] or "MEDIUM",
                    "simulated": bool(row[5]) if row[5] is not None else True,
                    "notes": row[6],
                    "matching_assets": set(aff_ids),
                    "relevance_reasons": [relevance],
                    "recovery_action_id": act_id,
                    "recovery_action_name": row[9],
                    "action_type": row[10],
                    "action_status": row[11],
                    "action_notes": row[12],
                    "evidence_path_summary": row[13],
                }
            else:
                if relevance not in aggregated_matches[key]["relevance_reasons"]:
                    aggregated_matches[key]["relevance_reasons"].append(relevance)
                aggregated_matches[key]["matching_assets"].update(aff_ids)
    except Exception as e:
        logger.error(f"Error querying incident memory for root cause '{clean_id}': {e}")
        raise RuntimeError(f"Database error querying incident memory for root cause '{clean_id}': {e}") from e

    # 2. Query: Overlapping affected critical services (AFFECTED)
    if affected_ids:
        cypher_affected = """
        MATCH (inc:Incident)-[:AFFECTED]->(aff:InfrastructureNode)
        WHERE aff.id IN $affected_ids
        OPTIONAL MATCH (inc)-[:TRIGGERED_BY]->(src:InfrastructureNode)
        OPTIONAL MATCH (inc)-[:USED_ACTION]->(act:RecoveryAction)
        OPTIONAL MATCH (inc)-[:SUPPORTED_BY]->(evd:EvidenceRecord)
        RETURN inc.id, inc.title, inc.timestamp, inc.failure_source, inc.severity, inc.simulated, inc.notes,
               aff.id AS matched_asset_id,
               act.id, act.action_name, act.action_type, act.status, act.notes,
               evd.path_summary
        """
        try:
            results_aff = db.query(cypher_affected, {"affected_ids": affected_ids})
            for row in results_aff:
                inc_id = row[0]
                if not inc_id:
                    continue
                matched_asset = row[7]
                act_id = row[8]
                key = f"{inc_id}::{act_id or 'NO_ACT'}"

                relevance = (
                    f"Overlapping affected service: Prior incident '{row[1]}' impacted asset {matched_asset}, "
                    f"which is also exposed in the current incident."
                )

                if key not in aggregated_matches:
                    aggregated_matches[key] = {
                        "incident_id": inc_id,
                        "title": row[1] or "",
                        "timestamp": row[2] or "",
                        "failure_source": row[3] or "",
                        "severity": row[4] or "MEDIUM",
                        "simulated": bool(row[5]) if row[5] is not None else True,
                        "notes": row[6],
                        "matching_assets": {matched_asset},
                        "relevance_reasons": [relevance],
                        "recovery_action_id": act_id,
                        "recovery_action_name": row[9],
                        "action_type": row[10],
                        "action_status": row[11],
                        "action_notes": row[12],
                        "evidence_path_summary": row[13],
                    }
                else:
                    if relevance not in aggregated_matches[key]["relevance_reasons"]:
                        aggregated_matches[key]["relevance_reasons"].append(relevance)
                    aggregated_matches[key]["matching_assets"].add(matched_asset)
        except Exception as e:
            logger.error(f"Error querying incident memory for overlapping assets: {e}")
            raise RuntimeError(f"Database error querying incident memory for overlapping assets: {e}") from e

    # 3. Query: Shared dependency cascade paths (SUPPORTED_BY)
    search_targets = affected_ids + [clean_id]
    cypher_evidence = """
    MATCH (inc:Incident)-[:SUPPORTED_BY]->(evd:EvidenceRecord)
    WHERE evd.source_id = $source_id OR evd.target_id IN $search_targets
    OPTIONAL MATCH (inc)-[:USED_ACTION]->(act:RecoveryAction)
    RETURN inc.id, inc.title, inc.timestamp, inc.failure_source, inc.severity, inc.simulated, inc.notes,
           evd.source_id, evd.target_id, evd.path_summary,
           act.id, act.action_name, act.action_type, act.status, act.notes
    """
    try:
        results_evd = db.query(cypher_evidence, {"source_id": clean_id, "search_targets": search_targets})
        for row in results_evd:
            inc_id = row[0]
            if not inc_id:
                continue
            evd_src = row[7]
            evd_tgt = row[8]
            path_sum = row[9]
            act_id = row[10]
            key = f"{inc_id}::{act_id or 'NO_ACT'}"

            relevance = (
                f"Shared dependency path: Prior incident recorded cascade evidence from {evd_src} to {evd_tgt} "
                f"('{path_sum}')."
            )

            if key not in aggregated_matches:
                aggregated_matches[key] = {
                    "incident_id": inc_id,
                    "title": row[1] or "",
                    "timestamp": row[2] or "",
                    "failure_source": row[3] or "",
                    "severity": row[4] or "MEDIUM",
                    "simulated": bool(row[5]) if row[5] is not None else True,
                    "notes": row[6],
                    "matching_assets": {evd_tgt},
                    "relevance_reasons": [relevance],
                    "recovery_action_id": act_id,
                    "recovery_action_name": row[11],
                    "action_type": row[12],
                    "action_status": row[13],
                    "action_notes": row[14],
                    "evidence_path_summary": path_sum,
                }
            else:
                if relevance not in aggregated_matches[key]["relevance_reasons"]:
                    aggregated_matches[key]["relevance_reasons"].append(relevance)
                aggregated_matches[key]["matching_assets"].add(evd_tgt)
                if not aggregated_matches[key]["evidence_path_summary"]:
                    aggregated_matches[key]["evidence_path_summary"] = path_sum
    except Exception as e:
        logger.error(f"Error querying incident memory for evidence paths: {e}")
        raise RuntimeError(f"Database error querying incident memory for evidence paths: {e}") from e

    # Build final list of typed matches
    matches: list[HistoricalIncidentMatch] = []
    for item in aggregated_matches.values():
        outcome_type, outcome_desc = classify_action_outcome(
            status=item["action_status"],
            notes=item["action_notes"] or item["notes"],
            is_simulated=bool(item.get("simulated", False)),
        )
        combined_reasons = "; ".join(item["relevance_reasons"])
        match_obj = HistoricalIncidentMatch(
            incident_id=item["incident_id"],
            title=item["title"],
            timestamp=item["timestamp"],
            failure_source=item["failure_source"],
            severity=item["severity"],
            simulated=item["simulated"],
            relevance_reason=combined_reasons,
            matching_assets=sorted(list(item["matching_assets"])),
            recovery_action_id=item["recovery_action_id"],
            recovery_action_name=item["recovery_action_name"],
            action_type=item["action_type"],
            action_status=item["action_status"],
            outcome_type=outcome_type,
            outcome_description=outcome_desc,
            evidence_path_summary=item["evidence_path_summary"],
            notes=item["notes"],
        )
        matches.append(match_obj)

    # Deterministic sort: timestamp descending, incident_id ascending
    matches.sort(key=lambda m: (-len(m.relevance_reason), m.incident_id, m.recovery_action_id or ""))
    return matches


def record_investigation_memory(
    investigation: InvestigationResult,
    ripple_scores: list[ScoreBreakdown],
    recovery_plan: Optional[RecoveryPlan] = None,
    incident_id: Optional[str] = None,
    notes: Optional[str] = None,
    client: Optional[FalkorDBClient] = None,
) -> dict[str, Any]:
    """Explicitly records an investigation summary, evidence paths, and proposed recovery actions
    into FalkorDB incident memory.
    
    Guarantees:
    - Only called upon explicit request (never implicitly during read-only investigation).
    - Idempotent writes via MERGE (repeated invocations update rather than duplicate).
    - Preserves infrastructure operational statuses (never mutates n.status on InfrastructureNode).
    - Distinguishes proposed/simulated actions from confirmed real-world outcomes.
    
    Returns:
        dict[str, Any]: Persistence summary with node and relationship IDs.
    """
    db = client or db_client
    source_id = validate_node_id(investigation.source_node_id)
    now_iso = datetime.now(timezone.utc).isoformat()

    # Stable deterministic incident ID if none provided
    inc_id = incident_id or f"INC-AGENT-{source_id}"
    inc_title = f"Investigation: Cascading Exposure from {investigation.source_node_name} ({source_id})"
    root_cause = "Substation Electrical Outage" if "SUB" in source_id else "Infrastructure Component Failure"
    severity = "CRITICAL" if investigation.critical_services_count > 0 else "HIGH"

    investigation_notes = (
        notes
        or f"Deterministic agent investigation. Total affected: {investigation.total_affected_count}, "
           f"Critical services: {investigation.critical_services_count}. Simulated in-memory."
    )

    # 1. Merge Incident node (Idempotent)
    cypher_inc = """
    MERGE (inc:Incident {id: $inc_id})
    SET inc.title = $title,
        inc.failure_source = $source_id,
        inc.timestamp = $timestamp,
        inc.root_cause_type = $root_cause_type,
        inc.severity = $severity,
        inc.simulated = true,
        inc.resolved = false,
        inc.notes = $notes
    """
    db.query(cypher_inc, {
        "inc_id": inc_id,
        "title": inc_title,
        "source_id": source_id,
        "timestamp": now_iso,
        "root_cause_type": root_cause,
        "severity": severity,
        "notes": investigation_notes,
    })

    # 2. Link TRIGGERED_BY to source InfrastructureNode
    cypher_trigger = """
    MATCH (inc:Incident {id: $inc_id}), (src:InfrastructureNode {id: $source_id})
    MERGE (inc)-[:TRIGGERED_BY]->(src)
    """
    db.query(cypher_trigger, {"inc_id": inc_id, "source_id": source_id})

    # 3. Link AFFECTED relationships to impacted assets
    affected_links_count = 0
    for finding in investigation.affected_services:
        cypher_aff = """
        MATCH (inc:Incident {id: $inc_id}), (tgt:InfrastructureNode {id: $target_id})
        MERGE (inc)-[:AFFECTED]->(tgt)
        """
        db.query(cypher_aff, {"inc_id": inc_id, "target_id": finding.asset_id})
        affected_links_count += 1

    # 4. Record EvidenceRecords for discovered cascade paths
    evidence_records_count = 0
    for finding in investigation.affected_services:
        if finding.evidence_paths:
            primary_path = finding.evidence_paths[0]
            evd_id = f"EVD-{inc_id}-{finding.asset_id}"
            cypher_evd = """
            MATCH (inc:Incident {id: $inc_id})
            MERGE (evd:EvidenceRecord {id: $evd_id})
            SET evd.source_id = $source_id,
                evd.target_id = $target_id,
                evd.path_hops = $path_hops,
                evd.path_summary = $path_summary,
                evd.confidence = $confidence
            MERGE (inc)-[:SUPPORTED_BY]->(evd)
            """
            db.query(cypher_evd, {
                "inc_id": inc_id,
                "evd_id": evd_id,
                "source_id": source_id,
                "target_id": finding.asset_id,
                "path_hops": primary_path.hops,
                "path_summary": primary_path.summary,
                "confidence": 0.95,
            })
            evidence_records_count += 1

    # 5. Record Proposed/Simulated RecoveryActions
    actions_recorded_count = 0
    if recovery_plan and recovery_plan.actions:
        for action in recovery_plan.actions:
            act_id = f"ACT-{inc_id}-{action.action_id}"
            cypher_act = """
            MATCH (inc:Incident {id: $inc_id})
            MERGE (act:RecoveryAction {id: $act_id})
            SET act.action_name = $action_name,
                act.action_type = $action_type,
                act.target_node_id = $target_node_id,
                act.estimated_hours = $estimated_hours,
                act.expected_benefit = $expected_benefit,
                act.status = 'PROPOSED',
                act.notes = $notes
            MERGE (inc)-[:USED_ACTION]->(act)
            """
            action_notes = (
                f"Proposed intervention for plan '{recovery_plan.plan_name}'. "
                f"Supplier: {action.supplier_id or 'N/A'}. "
                f"Net benefit score: {action.net_benefit_score}. Simulated in-memory."
            )
            db.query(cypher_act, {
                "inc_id": inc_id,
                "act_id": act_id,
                "action_name": f"{action.action_type}: {action.description[:60]}",
                "action_type": action.action_type,
                "target_node_id": action.target_id,
                "estimated_hours": action.estimated_hours,
                "expected_benefit": action.description,
                "notes": action_notes,
            })

            # Link action to target node if node exists
            cypher_act_tgt = """
            MATCH (act:RecoveryAction {id: $act_id}), (tgt:InfrastructureNode {id: $target_id})
            MERGE (act)-[:TARGETS]->(tgt)
            """
            db.query(cypher_act_tgt, {"act_id": act_id, "target_id": action.target_id})
            actions_recorded_count += 1

    logger.info(
        f"Persisted investigation memory for '{inc_id}': {affected_links_count} affected links, "
        f"{evidence_records_count} evidence records, {actions_recorded_count} proposed actions."
    )

    return {
        "incident_id": inc_id,
        "source_id": source_id,
        "affected_links_count": affected_links_count,
        "evidence_records_count": evidence_records_count,
        "actions_recorded_count": actions_recorded_count,
        "persisted_at": now_iso,
        "is_idempotent": True,
    }
