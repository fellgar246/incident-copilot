"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, listIncidents, simulateIncident } from "@/lib/api";
import { formatTime, formatUsd, probableCause } from "@/lib/format";
import { DEMO_SERVICES } from "@/lib/product-surface";
import { INCIDENT_STATUSES, SCENARIOS, type Incident, type IncidentStatus, type ScenarioId } from "@/lib/types";
import { ConfidenceMeter, EmptyState, ErrorBanner, Loading, SeverityBadge, StatusChip, CopyId } from "./ui";

const SCENARIO_LABELS: Record<ScenarioId, string> = {
  deployment_regression: "Deployment regression",
  connection_pool_exhaustion: "Connection pool exhaustion",
  queue_backlog: "Queue backlog",
  false_positive: "False positive",
};

export function IncidentList() {
  const [incidents, setIncidents] = useState<Incident[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<IncidentStatus | "">("");
  const [service, setService] = useState("");
  const [pending, setPending] = useState<ScenarioId | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const rows = await listIncidents({ status, service });
      rows.sort((a, b) => Date.parse(b.started_at) - Date.parse(a.started_at));
      setIncidents(rows);
    } catch (cause) {
      setIncidents([]);
      setError(cause instanceof ApiError ? cause.message : "Could not load incidents.");
    }
  }, [status, service]);

  useEffect(() => {
    void load();
  }, [load]);

  async function run(scenario: ScenarioId) {
    setPending(scenario);
    setError(null);
    try {
      const created = await simulateIncident(scenario);
      window.location.assign(`/incidents/${created.incident_id}`);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Simulation failed.");
      setPending(null);
    }
  }

  const simulateButton = (
    <div className="row-actions">
      <button type="button" data-testid="run-simulation" disabled={pending !== null} onClick={() => void run("deployment_regression")}>
        {pending === "deployment_regression" ? "Running…" : "Run simulation"}
      </button>
      <details className="menu">
        <summary className="button secondary">Other scenarios</summary>
        <div className="menu-panel">
          {SCENARIOS.filter((item) => item !== "deployment_regression").map((scenario) => (
            <button key={scenario} type="button" disabled={pending !== null} onClick={() => void run(scenario)}>
              {SCENARIO_LABELS[scenario]}
            </button>
          ))}
        </div>
      </details>
    </div>
  );

  return (
    <section>
      <header className="page-head">
        <div>
          <h1>Incidents</h1>
          <p className="lede">Severity, service, status, and estimated AI cost for the demo environment.</p>
        </div>
        {simulateButton}
      </header>
      <div className="filters">
        <select aria-label="Status" value={status} onChange={(event) => setStatus(event.target.value as IncidentStatus | "")}>
          <option value="">All statuses</option>
          {INCIDENT_STATUSES.map((item) => (
            <option key={item} value={item}>{item}</option>
          ))}
        </select>
        <select aria-label="Service" value={service} onChange={(event) => setService(event.target.value)}>
          <option value="">All services</option>
          {DEMO_SERVICES.map((item) => (
            <option key={item} value={item}>{item}</option>
          ))}
        </select>
      </div>
      {error ? <ErrorBanner message={error} onRetry={() => void load()} /> : null}
      {incidents === null ? <Loading label="Loading incidents…" /> : null}
      {incidents && incidents.length === 0 && !error ? (
        <EmptyState
          title="No incidents yet"
          body="Run the deployment_regression simulation to walk the demo from alarm → investigation → approval → resolve."
          action={simulateButton}
        />
      ) : null}
      {incidents && incidents.length > 0 ? (
        <div className="list">
          <div className="list-head">
            <span>Severity</span>
            <span>Service</span>
            <span>Probable cause</span>
            <span>Status</span>
            <span>Started</span>
            <span>Confidence</span>
            <span>AI cost</span>
          </div>
          {incidents.map((incident) => (
            <div key={incident.incident_id} className="incident-row" data-testid="incident-row">
              <SeverityBadge severity={incident.severity} />
              <span>{incident.service}</span>
              <span className="title">
                <a href={`/incidents/${incident.incident_id}`}>
                  <strong>{probableCause(incident)}</strong>
                </a>
                <CopyId value={incident.incident_id} label="incident id" />
              </span>
              <StatusChip status={incident.status} />
              <a href={`/incidents/${incident.incident_id}`}>{formatTime(incident.started_at)}</a>
              <ConfidenceMeter value={incident.confidence} />
              <span className="mono">{formatUsd(incident.estimated_ai_cost_usd)}</span>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
