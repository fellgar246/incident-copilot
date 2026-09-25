import type {
  AgentRun,
  AgentRunsResponse,
  CostMetrics,
  EvaluationSummary,
  Incident,
  IncidentEvent,
  IncidentStatus,
  ScenarioId,
} from "./types";

const ACTOR = "human:demo";

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export function apiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");
  return configured || "http://127.0.0.1:8000";
}

function newIdempotencyKey(prefix: string): string {
  const random =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${random}`;
}

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

function errorMessage(body: unknown, fallback: string): string {
  if (typeof body === "string" && body) return body;
  if (body && typeof body === "object") {
    const record = body as { detail?: unknown; error?: unknown };
    const detail = record.detail ?? record.error;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object") {
      const nested = detail as { error?: unknown; decision?: unknown };
      if (typeof nested.error === "string") return nested.error;
      if (nested.decision === "DENIED") return "Denied — missing valid approval";
    }
  }
  return fallback;
}

export function isDenied(error: unknown): boolean {
  if (!(error instanceof ApiError) || error.status !== 403) return false;
  const body = error.body;
  if (body && typeof body === "object") {
    const detail = (body as { detail?: unknown }).detail;
    if (detail && typeof detail === "object" && (detail as { decision?: string }).decision === "DENIED") {
      return true;
    }
  }
  return error.message.toLowerCase().includes("denied") || error.message.toLowerCase().includes("approval");
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      ...init,
      headers,
      cache: "no-store",
    });
  } catch (cause) {
    throw new ApiError(0, "The API is unreachable. Start it with make run-api.", cause);
  }
  const body = await parseBody(response);
  if (!response.ok) {
    throw new ApiError(response.status, errorMessage(body, response.statusText), body);
  }
  return body as T;
}

export function listIncidents(filters?: {
  status?: IncidentStatus | "";
  service?: string;
}): Promise<Incident[]> {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.service) params.set("service", filters.service);
  const query = params.toString();
  return request<Incident[]>(`/incidents${query ? `?${query}` : ""}`);
}

export function getIncident(id: string): Promise<Incident> {
  return request<Incident>(`/incidents/${encodeURIComponent(id)}`);
}

export function listEvents(id: string): Promise<IncidentEvent[]> {
  return request<IncidentEvent[]>(`/incidents/${encodeURIComponent(id)}/events`);
}

export function simulateIncident(scenario: ScenarioId): Promise<Incident> {
  return request<Incident>("/incidents/simulate", {
    method: "POST",
    headers: { "Idempotency-Key": newIdempotencyKey(scenario) },
    body: JSON.stringify({
      scenario,
      seed: newIdempotencyKey(scenario),
      simulation_id: newIdempotencyKey("sim"),
    }),
  });
}

export function investigateIncident(id: string): Promise<AgentRun> {
  return request<AgentRun>(`/incidents/${encodeURIComponent(id)}/investigate`, {
    method: "POST",
    headers: { "Idempotency-Key": newIdempotencyKey("investigate") },
  });
}

export function listAgentRuns(id: string): Promise<AgentRunsResponse> {
  return request<AgentRunsResponse>(`/incidents/${encodeURIComponent(id)}/agent-runs`);
}

export function approveIncident(id: string, approvalId: string): Promise<Incident> {
  return request<Incident>(`/incidents/${encodeURIComponent(id)}/approve`, {
    method: "POST",
    headers: {
      "Idempotency-Key": newIdempotencyKey("approve"),
      "X-Actor": ACTOR,
    },
    body: JSON.stringify({ approval_id: approvalId }),
  });
}

export function rejectIncident(id: string, approvalId: string): Promise<Incident> {
  return request<Incident>(`/incidents/${encodeURIComponent(id)}/reject`, {
    method: "POST",
    headers: {
      "Idempotency-Key": newIdempotencyKey("reject"),
      "X-Actor": ACTOR,
    },
    body: JSON.stringify({ approval_id: approvalId, reason: "Rejected from the dashboard" }),
  });
}

export function remediateIncident(id: string, approvalId: string): Promise<Incident> {
  return request<Incident>(`/incidents/${encodeURIComponent(id)}/remediate`, {
    method: "POST",
    headers: {
      "Idempotency-Key": newIdempotencyKey("remediate"),
      "X-Actor": ACTOR,
    },
    body: JSON.stringify({ approval_id: approvalId }),
  });
}

export function getCosts(): Promise<CostMetrics> {
  return request<CostMetrics>("/metrics/costs");
}

export function getEvaluations(): Promise<EvaluationSummary> {
  return request<EvaluationSummary>("/evaluations");
}
