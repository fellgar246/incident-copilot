/** Public API shapes consumed by the dashboard. */

export const INCIDENT_STATUSES = [
  "DETECTED",
  "QUEUED",
  "INVESTIGATING",
  "DIAGNOSED",
  "REMEDIATION_PROPOSED",
  "AWAITING_APPROVAL",
  "REJECTED",
  "APPROVED",
  "REMEDIATING",
  "FAILED",
  "RESOLVED",
] as const;

export type IncidentStatus = (typeof INCIDENT_STATUSES)[number];

export const SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"] as const;
export type Severity = (typeof SEVERITIES)[number];

export const SCENARIOS = [
  "deployment_regression",
  "connection_pool_exhaustion",
  "queue_backlog",
  "false_positive",
] as const;

export type ScenarioId = (typeof SCENARIOS)[number];

export const HAPPY_PATH: IncidentStatus[] = [
  "DETECTED",
  "QUEUED",
  "INVESTIGATING",
  "DIAGNOSED",
  "REMEDIATION_PROPOSED",
  "AWAITING_APPROVAL",
  "APPROVED",
  "REMEDIATING",
  "RESOLVED",
];

export type EvidenceKind = "observed_evidence" | "retrieved_guidance" | "inference";

export interface Evidence {
  evidence_id: string;
  kind: EvidenceKind;
  source: string;
  summary: string;
  observed_at: string;
  payload: Record<string, unknown>;
}

export interface Diagnosis {
  summary: string;
  probable_cause: string;
  confidence: number;
  evidence: Evidence[];
  retrieved_sources: string[];
  alternative_hypotheses: string[];
  recommended_action: string;
  requires_approval: boolean;
  destructive: boolean;
}

export interface Proposal {
  proposal_id: string;
  incident_id: string;
  action: string;
  rationale: string;
  requires_approval: boolean;
}

export interface Approval {
  approval_id: string;
  incident_id: string;
  status: "PENDING" | "GRANTED" | "REJECTED" | "EXPIRED";
  actor: string;
  created_at: string;
  expires_at: string;
  decided_at: string | null;
  proposal_id: string | null;
}

export interface Incident {
  incident_id: string;
  service: string;
  severity: Severity;
  status: IncidentStatus;
  alarm_name: string;
  started_at: string;
  updated_at: string;
  correlation_id: string;
  diagnosis: Diagnosis | null;
  confidence: number | null;
  recommended_action: string | null;
  approval_status: string | null;
  agent_run_id: string | null;
  estimated_ai_cost_usd: number;
  simulation_id: string | null;
  source_event_id: string | null;
  active_remediation_id: string | null;
  approval_id: string | null;
  proposal: Proposal | null;
  approval: Approval | null;
}

export interface IncidentEvent {
  event_id: string;
  incident_id: string;
  event_type: string;
  timestamp: string;
  actor: string;
  payload: Record<string, unknown>;
  from_status: IncidentStatus | null;
  to_status: IncidentStatus | null;
}

export interface AgentRun {
  agent_run_id: string;
  incident_id: string;
  correlation_id: string;
  status: string;
  model: string;
  model_calls: number;
  input_tokens: number;
  output_tokens: number;
  tool_calls: number;
  rag_calls: number;
  runtime_ms: number;
  estimated_cost_usd: number;
  stop_reason: string | null;
  idempotency_key: string | null;
  created_at: string;
  updated_at: string;
  tool_names: string[];
}

export interface TraceSpan {
  name: string;
  span_id: string;
  parent_span_id: string | null;
  attributes: Record<string, unknown>;
  children: TraceSpan[];
}

export interface AgentRunsResponse {
  runs: AgentRun[];
  trace: {
    incident_id: string;
    spans: TraceSpan[];
  };
  EstimatedCostPerIncident: number;
  TokensPerIncident: number;
  ToolCallsPerIncident: number;
  RuntimePerIncident: number;
  RagCallsPerIncident: number;
}

export interface CostSeries {
  incidents_total: number;
  incidents_by_status: Record<string, number>;
  investigation_latency: number;
  tool_error_rate: number;
  queue_age: number;
  dlq_messages: number;
  llm_calls: number;
  input_tokens: number;
  output_tokens: number;
  agent_turns: number;
  tool_calls: number;
  rag_calls: number;
  confidence: number | null;
  evaluation_score: number | null;
  estimated_cost: number;
}

export interface CostMetrics {
  log_retention_days: number;
  series: CostSeries;
  incidents: Array<{
    incident_id: string;
    EstimatedCostPerIncident: number;
    TokensPerIncident: number;
    ToolCallsPerIncident: number;
    RuntimePerIncident: number;
    RagCallsPerIncident: number;
  }>;
}

export interface EvaluationSummary {
  profile: string;
  case_count: number;
  evaluation_pass_rate: number;
  diagnosis_accuracy: number;
  groundedness: number;
  unsafe_action_count: number;
  avg_tool_calls: number;
  avg_estimated_cost: number;
  passed?: boolean;
  cohorts?: string[];
  gates?: Record<string, boolean>;
  [key: string]: unknown;
}
