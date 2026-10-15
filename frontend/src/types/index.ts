/**
 * TypeScript type definitions for RippleMap Frontend.
 * Grounded strictly in the backend schema (app.schema).
 */

export interface SourceNode {
  id: string;
  name: string;
  entity_type: string;
  criticality: string;
  status: string;
  zone: string;
}

export interface EvidencePath {
  node_ids: string[];
  relationship_types: string[];
  hops: number;
  summary: string;
}

export interface AlternateSupplyDetail {
  supplier_id: string;
  supplier_name: string;
  supplier_type: string;
  supplier_status: string;
  rel_type: string;
  dependency_type: string;
  is_redundant: boolean;
  estimated_restoration_hours: number;
  description: string;
  is_viable: boolean;
}

export interface BackupDetail {
  generator_id: string;
  generator_name: string;
  status: string;
  capacity_rating: string;
  buffer_hours: number;
  notes: string;
  dependency_type: string;
  confidence: number;
  is_ready: boolean;
  is_failed: boolean;
  is_insufficient: boolean;
  has_uncertain_capacity: boolean;
}

export interface AffectedAssetFinding {
  finding_id: string;
  asset_id: string;
  asset_name: string;
  entity_type: string;
  criticality: string;
  status: string;
  classification: string;
  direct_distance: number;
  evidence_paths: EvidencePath[];
  alternate_supply_available: boolean;
  alternate_supply_details: AlternateSupplyDetail[];
  backup_available: boolean;
  backup_details: BackupDetail[];
  simulated_outcome: string;
  assumptions: string[];
}

export interface ScoreBreakdown {
  asset_id: string;
  asset_name: string;
  criticality: string;
  inherent_score: number;
  downstream_impact_score: number;
  multipath_vulnerability_score: number;
  spof_penalty: number;
  mitigation_credit: number;
  backup_credit: number;
  capacity_penalty: number;
  failed_contingency_penalty: number;
  total_score: number;
  confidence: number;
  missing_data_notes: string[];
  formula_explanation: string;
}

export interface CandidateAction {
  action_id: string;
  action_type: string;
  target_id: string;
  target_name: string;
  supplier_id: string | null;
  supplier_name: string | null;
  dependency_type: string;
  is_feasible: boolean;
  rejection_reason: string | null;
  has_capacity_warning: boolean;
  capacity_ratio: number;
  estimated_hours: number;
  preconditions: string[];
  protected_asset_ids: string[];
  unique_critical_services_protected: number;
  residual_affected_count: number;
  net_benefit_score: number;
  description: string;
}

export interface RecoveryPlan {
  plan_id: string;
  plan_name: string;
  actions: CandidateAction[];
  total_estimated_hours: number;
  unique_critical_services_protected: number;
  protected_asset_ids: string[];
  residual_affected_count: number;
  residual_critical_count: number;
  composite_benefit_score: number;
  feasibility_summary: string;
  tradeoffs_and_risks: string[];
  fully_protected_asset_ids: string[];
  partially_mitigated_asset_ids: string[];
  unresolved_asset_ids: string[];
}

export interface HistoricalIncidentMatch {
  incident_id: string;
  title: string;
  timestamp: string;
  failure_source: string;
  severity: string;
  simulated: boolean;
  relevance_reason: string;
  matching_assets: string[];
  recovery_action_id?: string;
  recovery_action_name?: string;
  action_type?: string;
  action_status?: string;
  outcome_type: string;
  outcome_description: string;
  evidence_path_summary?: string;
  notes?: string;
}

export interface GroundedAnswer {
  question: string;
  answer: string;
  supporting_asset_ids: string[];
  graph_paths: string[];
  relationship_types: string[];
  relevant_properties: Record<string, any>;
  unresolved_assumptions: string[];
  evidence_sufficient: boolean;
  confidence_score: number;
  llm_explanation?: string | null;
}

export interface AgentBriefing {
  incident_id: string;
  source_node_id: string;
  source_node_name: string;
  source_entity_type: string;
  source_criticality: string;
  source_status: string;
  timestamp: string;
  is_persisted_memory: boolean;
  investigation_summary: string;
  direct_findings: AffectedAssetFinding[];
  downstream_findings: AffectedAssetFinding[];
  evidence_paths: EvidencePath[];
  ripple_scores: ScoreBreakdown[];
  historical_incidents: HistoricalIncidentMatch[];
  candidate_actions: CandidateAction[];
  evaluated_plans: RecoveryPlan[];
  recommended_plan: RecoveryPlan | null;
  recommendation_rationale: string;
  grounded_answers: GroundedAnswer[];
  recommended_next_steps: string[];
  missing_data_and_assumptions: string[];
  confidence_assessment: Record<string, any>;
  llm_narrative?: string | null;
  llm_explanation_status: string;
}

export interface HealthResponse {
  status: string;
  database_connected: boolean;
  graph_name: string;
  host: string;
  port: number;
  node_count: number;
  relationship_count: number;
  groq_configured: boolean;
  groq_model: string;
}
