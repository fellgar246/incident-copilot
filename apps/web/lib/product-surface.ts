export const DASHBOARD_ROUTES = [
  "/incidents",
  "/incidents/[id]",
  "/evaluations",
  "/settings/costs",
] as const;

export const INCIDENT_LIST_COLUMNS = [
  "severity",
  "service",
  "status",
  "started_at",
  "probable_cause",
  "confidence",
  "estimated_ai_cost_usd",
] as const;

export const INCIDENT_DETAIL_SECTIONS = [
  "Overview",
  "Timeline",
  "AI Investigation",
  "Evidence",
  "Retrieved Knowledge",
  "Recommended Action",
  "Approval",
  "Execution",
  "Cost",
  "Trace",
] as const;

export const EVALUATION_METRICS = [
  "evaluation_pass_rate",
  "diagnosis_accuracy",
  "groundedness",
  "unsafe_action_count",
  "avg_tool_calls",
  "avg_estimated_cost",
] as const;

export const DEMO_SERVICES = [
  "payments-api",
  "orders-api",
  "notifications-worker",
] as const;

export const INVESTIGATION_TOOLS = [
  "query_logs",
  "query_metrics",
  "get_recent_deployments",
  "search_runbooks",
] as const;

export const COST_LIMITS_CLIENT_WRITABLE = false;
