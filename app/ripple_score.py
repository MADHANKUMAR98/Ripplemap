"""RippleScore — transparent, deterministic infrastructure risk and exposure ranking.

Derives explainable risk scores from inherent criticality, blast radius, multi-vector exposure,
shared upstream SPOF status, and verifiable mitigation/backup credits.
Scores are bounded [0, 100] and explicitly avoid fabricated failure probabilities.
"""

import re
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from app.db import FalkorDBClient, db_client
from app.schema import (
    ScoreBreakdown,
    RippleScoreResult,
    InvestigationResult,
    AffectedAssetFinding,
    ImpactClassification,
)
from app.graph_queries import (
    get_node_by_id,
    get_downstream_paths,
    get_shared_upstream_analysis,
    get_backups_for_node,
    get_direct_dependencies,
)

logger = logging.getLogger(__name__)

# Transparent scoring weights (sum bounded to 100)
CRITICALITY_POINTS = {
    "Tier 1 - Life Safety": 40.0,
    "Tier 2 - Essential Service": 25.0,
    "Tier 3 - Operational Support": 12.0,
    "Tier 4 - Standard": 5.0,
}

DOWNSTREAM_WEIGHTS = {
    "Tier 1 - Life Safety": 10.0,
    "Tier 2 - Essential Service": 6.0,
    "Tier 3 - Operational Support": 2.0,
    "Tier 4 - Standard": 1.0,
}


def _extract_capacity_ratio(capacity_str: str, notes: str) -> float:
    """Extracts numeric capacity ratio (0.0 to 1.0) from capacity rating and notes."""
    combined = f"{capacity_str} {notes}".upper()
    percent_match = re.search(r"(\d+)%", combined)
    if percent_match:
        return float(percent_match.group(1)) / 100.0
    if "INSUFFICIENT" in combined:
        return 0.40  # Documented fallback ratio for insufficient status when uncalibrated
    return 1.0


def calculate_component_score(
    node_id: str,
    node_name: str,
    criticality: str,
    is_source: bool = False,
    is_spof: bool = False,
    downstream_nodes: Optional[list[dict[str, Any]]] = None,
    incoming_paths: Optional[list[Any]] = None,
    alternate_supplies: Optional[list[dict[str, Any]]] = None,
    backups: Optional[list[dict[str, Any]]] = None,
) -> ScoreBreakdown:
    """Calculates a deterministic ScoreBreakdown for an infrastructure component.
    
    Formula:
        TotalScore = clamp(
            InherentCriticality (0-40)
            + DownstreamImpact (0-35)
            + MultipathVulnerability (0-15)
            + SPOFPenalty (0-10)
            - MitigationCredit (0-20)
            - BackupCredit (0-15)
            + BackupCapacityPenalty (0-6)
            + FailedContingencyPenalty (0-8),
            0.0, 100.0
        )
    """
    missing_data_notes: list[str] = []
    confidence = 1.0

    # 1. Inherent Criticality Score (0 - 40)
    inherent_score = CRITICALITY_POINTS.get(criticality, 10.0)

    # 2. Downstream Impact Score (0 - 35)
    # Deduplicate unique downstream assets reached from this component
    downstream_impact = 0.0
    if downstream_nodes:
        seen_downstream = set()
        for d in downstream_nodes:
            did = d["id"]
            if did not in seen_downstream and did != node_id:
                seen_downstream.add(did)
                crit = d.get("criticality", "")
                downstream_impact += DOWNSTREAM_WEIGHTS.get(crit, 1.0)
    downstream_impact = min(35.0, downstream_impact)

    # 3. Multi-path Vulnerability Score (0 - 15)
    # Penalizes assets that have multiple unmitigated failure vectors arriving
    multipath_score = 0.0
    if not is_source and incoming_paths:
        incoming_rel_types = set()
        for p in incoming_paths:
            if hasattr(p, "relationship_types") and p.relationship_types:
                incoming_rel_types.add(p.relationship_types[-1])
            elif isinstance(p, dict) and p.get("rel_types"):
                incoming_rel_types.add(p["rel_types"][-1])

        unmitigated_vectors = len(incoming_rel_types)
        if alternate_supplies:
            mitigated_rels = {a.get("rel_type") for a in alternate_supplies}
            unmitigated_vectors = max(0, len(incoming_rel_types - mitigated_rels))

        if unmitigated_vectors == 1:
            multipath_score = 5.0
        elif unmitigated_vectors == 2:
            multipath_score = 10.0
        elif unmitigated_vectors >= 3:
            multipath_score = 15.0

    # 4. Shared Upstream SPOF Penalty (0 - 10)
    spof_penalty = 10.0 if is_spof else 0.0

    # 5. Mitigation Credit (0 - 20)
    mitigation_credit = 0.0
    if alternate_supplies:
        viable = [a for a in alternate_supplies if a.get("is_viable", True)]
        if viable:
            # Check if all incoming vectors are covered
            incoming_rels = set()
            if incoming_paths:
                for p in incoming_paths:
                    if hasattr(p, "relationship_types") and p.relationship_types:
                        incoming_rels.add(p.relationship_types[-1])
            mitigated_rels = {a.get("rel_type") for a in viable}
            if incoming_rels and incoming_rels.issubset(mitigated_rels):
                mitigation_credit = 20.0
            else:
                mitigation_credit = 10.0  # Partial mitigation

            # Check if restoration time is known
            for v in viable:
                if v.get("estimated_restoration_hours", 0.0) <= 0.0:
                    confidence -= 0.05
                    missing_data_notes.append(f"Alternate supply from {v.get('supplier_id')} missing restoration time.")

    # 6. Backup Credit & Penalties (0 - 15 Credit; Penalties up to +14)
    backup_credit = 0.0
    capacity_penalty = 0.0
    failed_penalty = 0.0

    if backups:
        for b in backups:
            is_failed = b.get("is_failed", False)
            is_insufficient = b.get("is_insufficient", False)
            has_uncertain = b.get("has_uncertain_capacity", False)

            if is_failed:
                failed_penalty += 8.0
                missing_data_notes.append(f"Backup generator {b.get('generator_id')} is FAILED; contingency is unavailable.")
            elif is_insufficient:
                ratio = _extract_capacity_ratio(b.get("capacity_rating", ""), b.get("notes", ""))
                backup_credit += 15.0 * ratio
                capacity_penalty += 6.0
                missing_data_notes.append(
                    f"Backup {b.get('generator_id')} capacity ratio is {int(ratio*100)}% (insufficient under peak load)."
                )
            elif has_uncertain:
                confidence -= 0.15
                backup_credit += 5.0
                missing_data_notes.append(f"Backup {b.get('generator_id')} capacity unmodeled; flagged as uncertainty.")
            else:
                backup_credit += 15.0

    backup_credit = min(15.0, backup_credit)

    # 7. Total Composite Score Calculation
    raw_score = (
        inherent_score
        + downstream_impact
        + multipath_score
        + spof_penalty
        - mitigation_credit
        - backup_credit
        + capacity_penalty
        + failed_penalty
    )
    total_score = max(0.0, min(100.0, round(raw_score, 1)))
    confidence = max(0.1, min(1.0, round(confidence, 2)))

    formula_explanation = (
        f"Inherent ({inherent_score:.0f}) + DownstreamImpact ({downstream_impact:.0f}) + "
        f"Multipath ({multipath_score:.0f}) + SPOF ({spof_penalty:.0f}) - "
        f"Mitigation ({mitigation_credit:.0f}) - Backup ({backup_credit:.0f}) + "
        f"Penalties ({capacity_penalty + failed_penalty:.0f}) = {total_score:.1f}"
    )

    return ScoreBreakdown(
        asset_id=node_id,
        asset_name=node_name,
        criticality=criticality,
        inherent_score=inherent_score,
        downstream_impact_score=downstream_impact,
        multipath_vulnerability_score=multipath_score,
        spof_penalty=spof_penalty,
        mitigation_credit=mitigation_credit,
        backup_credit=backup_credit,
        capacity_penalty=capacity_penalty,
        failed_contingency_penalty=failed_penalty,
        total_score=total_score,
        confidence=confidence,
        missing_data_notes=missing_data_notes,
        formula_explanation=formula_explanation,
    )


def compute_incident_ripple_scores(
    investigation: InvestigationResult,
    client: Optional[FalkorDBClient] = None
) -> RippleScoreResult:
    """Computes comprehensive, explainable RippleScores for the incident source
    and all affected downstream assets discovered in an investigation.
    
    Returns deterministic, ranked results from highest to lowest exposure risk.
    """
    db = client or db_client
    source_id = investigation.source_node_id
    timestamp = datetime.now(timezone.utc).isoformat()

    # 1. Analyze the incident source component
    source_node = get_node_by_id(source_id, client=db)
    spof_info = get_shared_upstream_analysis(source_id, client=db)
    is_source_spof = spof_info.get("is_shared_upstream_spof", False)

    # Compile all unique downstream assets from the investigation
    downstream_nodes_for_source = [
        {"id": f.asset_id, "criticality": f.criticality}
        for f in investigation.affected_services
    ]

    source_breakdown = calculate_component_score(
        node_id=source_id,
        node_name=investigation.source_node_name,
        criticality=source_node["criticality"] if source_node else "Tier 1 - Life Safety",
        is_source=True,
        is_spof=is_source_spof,
        downstream_nodes=downstream_nodes_for_source,
    )

    ranked_scores: list[ScoreBreakdown] = [source_breakdown]

    # 2. Score each affected downstream asset
    for finding in investigation.affected_services:
        # Determine any further downstream nodes reachable from this asset
        sub_paths = get_downstream_paths(finding.asset_id, max_depth=2, client=db)
        sub_downstream = [
            {"id": p["destination"]["id"], "criticality": p["destination"]["criticality"]}
            for p in sub_paths
        ]

        breakdown = calculate_component_score(
            node_id=finding.asset_id,
            node_name=finding.asset_name,
            criticality=finding.criticality,
            is_source=False,
            is_spof=False,
            downstream_nodes=sub_downstream,
            incoming_paths=finding.evidence_paths,
            alternate_supplies=finding.alternate_supply_details,
            backups=finding.backup_details,
        )
        ranked_scores.append(breakdown)

    # 3. Deterministic Sort: Total score descending, then Inherent score descending, then ID
    ranked_scores.sort(
        key=lambda s: (-s.total_score, -s.inherent_score, s.asset_id)
    )

    summary = (
        f"RippleScore risk ranking for {investigation.source_node_name} ({source_id}) evaluated "
        f"{len(ranked_scores)} components. Highest exposure risk: {ranked_scores[0].asset_name} "
        f"({ranked_scores[0].asset_id}) with score {ranked_scores[0].total_score}/100."
    )

    return RippleScoreResult(
        incident_source_id=source_id,
        incident_source_name=investigation.source_node_name,
        timestamp=timestamp,
        ranked_scores=ranked_scores,
        summary=summary,
    )
