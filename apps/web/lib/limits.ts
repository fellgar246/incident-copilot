/**
 * Effective dev limits shown read-only. They mirror the environment contract
 * and cannot be raised from the dashboard.
 */
export const TARGET_MONTHLY_COST_USD = 5;

export const EFFECTIVE_LIMITS: ReadonlyArray<{ name: string; value: string }> = [
  { name: "TARGET_MONTHLY_COST_USD", value: "5.00" },
  { name: "MAX_INCIDENTS_PER_DAY", value: "10" },
  { name: "MAX_AGENT_RUNS_PER_INCIDENT", value: "2" },
  { name: "MAX_AGENT_TURNS", value: "4" },
  { name: "MAX_TOOL_CALLS_PER_RUN", value: "8" },
  { name: "MAX_RAG_CALLS_PER_RUN", value: "2" },
  { name: "MAX_RAG_RESULTS", value: "4" },
  { name: "MAX_MODEL_INPUT_TOKENS_PER_CALL", value: "6000" },
  { name: "MAX_MODEL_OUTPUT_TOKENS_PER_CALL", value: "1200" },
  { name: "MAX_SESSION_SECONDS", value: "120" },
  { name: "LOG_RETENTION_DAYS", value: "7" },
];
