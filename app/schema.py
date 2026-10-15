"""Schema definitions and type models for Ripple City infrastructure entities and edges."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class EntityType(str, Enum):
    SUBSTATION = "Substation"
    WATER_PUMP = "WaterPump"
    HOSPITAL = "Hospital"
    CLINIC = "Clinic"
    MOBILE_TOWER = "MobileTower"
    CELL_TOWER = "MobileTower"  # Alias for backward compatibility
    EMERGENCY_CENTER = "EmergencyCenter"
    ROAD = "Road"
    BACKUP_GENERATOR = "BackupGenerator"
    ZONE = "InfrastructureZone"
    INCIDENT = "Incident"
    RECOVERY_ACTION = "RecoveryAction"
    EVIDENCE_RECORD = "EvidenceRecord"


class Criticality(str, Enum):
    TIER_1_CRITICAL = "Tier 1 - Life Safety"
    TIER_2_HIGH = "Tier 2 - Essential Service"
    TIER_3_MEDIUM = "Tier 3 - Operational Support"
    TIER_4_LOW = "Tier 4 - Standard"


class OperationalStatus(str, Enum):
    OPERATIONAL = "OPERATIONAL"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    OFFLINE = "OFFLINE"


class RelationshipType(str, Enum):
    SUPPLIES_POWER_TO = "SUPPLIES_POWER_TO"
    SUPPLIES_WATER_TO = "SUPPLIES_WATER_TO"
    SUPPORTS_COMMUNICATION_FOR = "SUPPORTS_COMMUNICATION_FOR"
    CONNECTS_TO = "CONNECTS_TO"
    HAS_BACKUP = "HAS_BACKUP"
    DEPENDS_ON = "DEPENDS_ON"
    LOCATED_IN = "LOCATED_IN"
    AFFECTED = "AFFECTED"
    TRIGGERED_BY = "TRIGGERED_BY"
    USED_ACTION = "USED_ACTION"
    TARGETS = "TARGETS"
    SUPPORTED_BY = "SUPPORTED_BY"


@dataclass
class InfrastructureNodeData:
    id: str
    name: str
    entity_type: EntityType
    criticality: Criticality
    status: OperationalStatus
    zone: str
    latitude: float
    longitude: float
    buffer_hours: float = 0.0  # Battery or fuel backup runway
    capacity_rating: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class RelationshipData:
    source_id: str
    target_id: str
    rel_type: RelationshipType
    dependency_type: str  # e.g., "primary_feed", "telemetry", "cooling_supply", "access_route"
    confidence: float     # e.g., 0.95 for direct physical link
    estimated_restoration_hours: float
    is_redundant: bool = False
    description: Optional[str] = None


@dataclass
class IncidentRecord:
    id: str
    title: str
    failure_source: str
    timestamp: str
    affected_nodes: list[str]
    root_cause_type: str
    severity: str
    simulated: bool = True
    notes: Optional[str] = None


@dataclass
class RecoveryActionRecord:
    id: str
    incident_id: str
    action_name: str
    action_type: str
    target_node_id: str
    estimated_hours: float
    expected_benefit: str
    status: str = "RECOMMENDED"
    notes: Optional[str] = None


@dataclass
class EvidenceRecordData:
    id: str
    incident_id: str
    source_id: str
    target_id: str
    path_hops: int
    path_summary: str
    relationship_types: list[str]
    confidence: float = 1.0


class ImpactClassification(str, Enum):
    DIRECT_DEPENDENCY = "DIRECT_DEPENDENCY"
    DOWNSTREAM_DEPENDENCY = "DOWNSTREAM_DEPENDENCY"
    POTENTIAL_SERVICE_IMPACT = "POTENTIAL_SERVICE_IMPACT"
    MITIGATED_BY_ALTERNATIVE = "MITIGATED_BY_ALTERNATIVE"
    BACKUP_UNAVAILABLE = "BACKUP_UNAVAILABLE"
    BACKUP_CAPACITY_INSUFFICIENT = "BACKUP_CAPACITY_INSUFFICIENT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass
class EvidencePath:
    node_ids: list[str]
    relationship_types: list[str]
    hops: int
    summary: str


@dataclass
class AffectedAssetFinding:
    finding_id: str
    asset_id: str
    asset_name: str
    entity_type: str
    criticality: str
    status: str
    classification: ImpactClassification
    direct_distance: int
    evidence_paths: list[EvidencePath]
    alternate_supply_available: bool
    alternate_supply_details: list[dict]
    backup_available: bool
    backup_details: list[dict]
    simulated_outcome: str
    assumptions: list[str]


@dataclass
class InvestigationResult:
    incident_id: str
    source_node_id: str
    source_node_name: str
    source_entity_type: str
    source_status: str
    investigation_status: str
    summary: str
    total_affected_count: int
    direct_dependency_count: int
    downstream_dependency_count: int
    critical_services_count: int
    affected_services: list[AffectedAssetFinding]
    available_mitigations: list[dict]
    backup_alerts: list[dict]
    recommended_checks: list[str]
    assumptions: list[str]
    timestamp: str


@dataclass
class ScoreBreakdown:
    asset_id: str
    asset_name: str
    criticality: str
    inherent_score: float              # Base points for inherent criticality (0-40)
    downstream_impact_score: float     # Reachable downstream critical services impact (0-35)
    multipath_vulnerability_score: float # Multi-vector exposure / unmitigated failure paths (0-15)
    spof_penalty: float                # Penalty for shared upstream Single Point of Failure (0-10)
    mitigation_credit: float           # Subtraction for verified alternate supply routes (0-20)
    backup_credit: float               # Subtraction for operational backup generator (0-15)
    capacity_penalty: float            # Addition for insufficient backup capacity (e.g. +6)
    failed_contingency_penalty: float  # Addition for failed/unavailable backup generator (e.g. +8)
    total_score: float                 # Clamped [0, 100]
    confidence: float                  # Data confidence [0.0, 1.0] reflecting completeness of properties
    missing_data_notes: list[str]
    formula_explanation: str


@dataclass
class RippleScoreResult:
    incident_source_id: str
    incident_source_name: str
    timestamp: str
    ranked_scores: list[ScoreBreakdown]
    summary: str


@dataclass
class CandidateAction:
    action_id: str
    action_type: str                   # "SWITCH_ALTERNATE_SUPPLY", "DEPLOY_BACKUP", "RESTORE_COMPONENT"
    target_id: str
    target_name: str
    supplier_id: Optional[str]         # e.g. "SUB-002" or "GEN-002"
    supplier_name: Optional[str]
    dependency_type: str
    is_feasible: bool
    rejection_reason: Optional[str]
    has_capacity_warning: bool
    capacity_ratio: float              # 1.0 = 100%, 0.40 = 40%
    estimated_hours: float
    preconditions: list[str]
    protected_asset_ids: list[str]
    unique_critical_services_protected: int
    residual_affected_count: int
    net_benefit_score: float
    description: str
    fully_protected_asset_ids: list[str] = field(default_factory=list)
    partially_mitigated_asset_ids: list[str] = field(default_factory=list)


@dataclass
class RecoveryPlan:
    plan_id: str
    plan_name: str
    actions: list[CandidateAction]
    total_estimated_hours: float
    unique_critical_services_protected: int
    protected_asset_ids: list[str]
    residual_affected_count: int
    residual_critical_count: int
    composite_benefit_score: float
    feasibility_summary: str
    tradeoffs_and_risks: list[str]
    fully_protected_asset_ids: list[str] = field(default_factory=list)
    partially_mitigated_asset_ids: list[str] = field(default_factory=list)
    unresolved_asset_ids: list[str] = field(default_factory=list)


@dataclass
class OptimizationResult:
    incident_source_id: str
    incident_source_name: str
    baseline_affected_count: int
    baseline_critical_count: int
    candidate_actions: list[CandidateAction]
    evaluated_plans: list[RecoveryPlan]
    recommended_plan: Optional[RecoveryPlan]
    recommendation_rationale: str
    rejected_actions: list[CandidateAction]
    assumptions: list[str]
    timestamp: str


class OutcomeType(str, Enum):
    CONFIRMED_SUCCESSFUL = "CONFIRMED_SUCCESSFUL"
    CONFIRMED_FAILED = "CONFIRMED_FAILED"
    RECORDED_ACTION_TAKEN = "RECORDED_ACTION_TAKEN"
    PROPOSED_ACTION = "PROPOSED_ACTION"
    SIMULATED_OUTCOME = "SIMULATED_OUTCOME"
    MISSING_OUTCOME_DATA = "MISSING_OUTCOME_DATA"


@dataclass
class HistoricalIncidentMatch:
    incident_id: str
    title: str
    timestamp: str
    failure_source: str
    severity: str
    simulated: bool
    relevance_reason: str
    matching_assets: list[str]
    recovery_action_id: Optional[str] = None
    recovery_action_name: Optional[str] = None
    action_type: Optional[str] = None
    action_status: Optional[str] = None
    outcome_type: OutcomeType = OutcomeType.MISSING_OUTCOME_DATA
    outcome_description: str = ""
    evidence_path_summary: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class GroundedAnswer:
    question: str
    answer: str
    supporting_asset_ids: list[str]
    graph_paths: list[str]
    relationship_types: list[str]
    relevant_properties: dict[str, Any] = field(default_factory=dict)
    unresolved_assumptions: list[str] = field(default_factory=list)
    evidence_sufficient: bool = True
    confidence_score: float = 1.0
    llm_explanation: Optional[str] = None


@dataclass
class AgentBriefing:
    incident_id: str
    source_node_id: str
    source_node_name: str
    source_entity_type: str
    source_criticality: str
    source_status: str
    timestamp: str
    is_persisted_memory: bool
    investigation_summary: str
    direct_findings: list[AffectedAssetFinding]
    downstream_findings: list[AffectedAssetFinding]
    evidence_paths: list[EvidencePath]
    ripple_scores: list[ScoreBreakdown]
    historical_incidents: list[HistoricalIncidentMatch]
    candidate_actions: list[CandidateAction]
    evaluated_plans: list[RecoveryPlan]
    recommended_plan: Optional[RecoveryPlan]
    recommendation_rationale: str
    grounded_answers: list[GroundedAnswer]
    recommended_next_steps: list[str]
    missing_data_and_assumptions: list[str]
    confidence_assessment: dict[str, Any]
    memory_persistence_details: Optional[dict[str, Any]] = None
    llm_narrative: Optional[str] = None
    llm_explanation_status: str = "DETERMINISTIC_ONLY"




