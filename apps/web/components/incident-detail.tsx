"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  approveIncident,
  getIncident,
  investigateIncident,
  isDenied,
  listAgentRuns,
  listEvents,
  rejectIncident,
  remediateIncident,
} from "@/lib/api";
import {
  formatTime,
  formatUsd,
  lifecycleIndex,
  readDenial,
  writeDenial,
  type DenialNotice,
} from "@/lib/format";
import { INCIDENT_DETAIL_SECTIONS } from "@/lib/product-surface";
import {
  HAPPY_PATH,
  type AgentRunsResponse,
  type Evidence,
  type Incident,
  type IncidentEvent,
  type TraceSpan,
} from "@/lib/types";
import { ConfidenceMeter, CopyId, ErrorBanner, Loading, SeverityBadge, StatusChip } from "./ui";

const TABS = [
  "overview",
  "timeline",
  "investigation",
  "evidence",
  "knowledge",
  "action",
  "approval",
  "execution",
  "cost",
  "trace",
] as const;

type TabId = (typeof TABS)[number];

function useIncidentId(): string | null {
  const [id, setId] = useState<string | null>(null);
  useEffect(() => {
    const parts = window.location.pathname.split("/").filter(Boolean);
    const segment = parts[1];
    if (segment && segment !== "_") setId(decodeURIComponent(segment));
  }, []);
  return id;
}

function tabFromLocation(): TabId {
  if (typeof window === "undefined") return "overview";
  const value = new URLSearchParams(window.location.search).get("tab");
  return TABS.includes(value as TabId) ? (value as TabId) : "overview";
}

export function IncidentDetail() {
  const incidentId = useIncidentId();
  const [incident, setIncident] = useState<Incident | null>(null);
  const [events, setEvents] = useState<IncidentEvent[]>([]);
  const [runs, setRuns] = useState<AgentRunsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>("overview");
  const [dialog, setDialog] = useState<"approve" | "reject" | null>(null);
  const [denial, setDenial] = useState<DenialNotice | null>(null);

  const load = useCallback(async (id: string) => {
    setError(null);
    try {
      const [nextIncident, nextEvents, nextRuns] = await Promise.all([
        getIncident(id),
        listEvents(id),
        listAgentRuns(id),
      ]);
      setIncident(nextIncident);
      setEvents(nextEvents);
      setRuns(nextRuns);
      setDenial(readDenial(id));
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not load the incident.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setTab(tabFromLocation());
  }, []);

  useEffect(() => {
    if (!incidentId) return;
    void load(incidentId);
  }, [incidentId, load]);

  function selectTab(next: TabId) {
    setTab(next);
    const url = new URL(window.location.href);
    url.searchParams.set("tab", next);
    window.history.replaceState(null, "", url);
  }

  async function act(label: string, work: () => Promise<void>) {
    if (!incidentId) return;
    setBusy(label);
    setError(null);
    try {
      await work();
      await load(incidentId);
    } catch (cause) {
      if (isDenied(cause)) {
        const message = cause instanceof ApiError ? cause.message : "Denied — missing valid approval";
        setDenial(writeDenial(incidentId, message));
        setError(null);
        selectTab("timeline");
      } else {
        setError(cause instanceof ApiError ? cause.message : "The request failed.");
      }
    } finally {
      setBusy(null);
      setDialog(null);
    }
  }

  if (!incidentId || loading) return <Loading label="Loading incident…" />;
  if (!incident) {
    return <ErrorBanner message={error || "Incident not found."} onRetry={() => void load(incidentId)} />;
  }

  const approvalId = incident.approval?.approval_id || incident.approval_id || "";
  const index = lifecycleIndex(incident.status);

  return (
    <section>
      <header className="detail-head">
        <div>
          <div className="chips">
            <SeverityBadge severity={incident.severity} />
            <StatusChip status={incident.status} />
            <span className="muted">{incident.service}</span>
          </div>
          <h1 style={{ marginTop: 8 }}>{incident.diagnosis?.probable_cause || incident.alarm_name}</h1>
          <p className="lede">{incident.alarm_name}</p>
        </div>
        <HeaderActions
          status={incident.status}
          busy={busy}
          canDecide={Boolean(approvalId)}
          onInvestigate={() => void act("investigate", async () => { await investigateIncident(incident.incident_id); })}
          onReview={() => selectTab("action")}
          onApprove={() => setDialog("approve")}
          onReject={() => setDialog("reject")}
          onExecute={() =>
            void act("execute", async () => {
              await remediateIncident(incident.incident_id, approvalId || "missing");
            })
          }
          onTrace={() => selectTab("trace")}
        />
      </header>

      <div className="stepper" data-testid="lifecycle">
        {HAPPY_PATH.map((step, stepIndex) => {
          const branch = (incident.status === "REJECTED" && step === "AWAITING_APPROVAL") || (incident.status === "FAILED" && step === "REMEDIATING");
          const className = branch ? "bad" : stepIndex < index ? "done" : stepIndex === index ? "current" : "";
          const label = branch ? incident.status : step;
          return <span key={step} className={`step ${className}`}>{label}</span>;
        })}
      </div>

      {denial ? (
        <div className="banner denied" role="alert" data-testid="denied-banner">
          Denied — missing valid approval. {denial.message}
        </div>
      ) : null}
      {error ? <ErrorBanner message={error} onRetry={() => void load(incident.incident_id)} /> : null}

      <div className="tabs" role="tablist">
        {TABS.map((item, itemIndex) => (
          <button key={item} type="button" role="tab" aria-selected={tab === item} onClick={() => selectTab(item)}>
            {INCIDENT_DETAIL_SECTIONS[itemIndex]}
          </button>
        ))}
      </div>

      <div className="split">
        <div className="stack">
          {tab === "overview" ? <Overview incident={incident} /> : null}
          {tab === "timeline" ? <Timeline events={events} denial={denial} /> : null}
          {tab === "investigation" ? <Investigation events={events} incident={incident} /> : null}
          {tab === "evidence" ? <EvidencePanel evidence={incident.diagnosis?.evidence ?? []} events={events} /> : null}
          {tab === "knowledge" ? <Knowledge incident={incident} /> : null}
          {tab === "action" ? <Action incident={incident} /> : null}
          {tab === "approval" ? <ApprovalPanel incident={incident} onApprove={() => setDialog("approve")} onReject={() => setDialog("reject")} /> : null}
          {tab === "execution" ? <Execution incident={incident} onAttempt={() => void act("execute", async () => { await remediateIncident(incident.incident_id, approvalId || "missing"); })} busy={busy === "execute"} /> : null}
          {tab === "cost" ? <CostPanel incident={incident} runs={runs} /> : null}
          {tab === "trace" ? <TracePanel runs={runs} /> : null}
        </div>
        <aside className="panel rail">
          <h2>Correlation</h2>
          <dl>
            <div><dt>incident_id</dt><dd><CopyId value={incident.incident_id} label="incident_id" /></dd></div>
            <div><dt>agent_run_id</dt><dd>{incident.agent_run_id ? <CopyId value={incident.agent_run_id} label="agent_run_id" /> : "—"}</dd></div>
            <div><dt>correlation_id</dt><dd><CopyId value={incident.correlation_id} label="correlation_id" /></dd></div>
            <div><dt>Started</dt><dd>{formatTime(incident.started_at)}</dd></div>
            <div><dt>Updated</dt><dd>{formatTime(incident.updated_at)}</dd></div>
            <div><dt>Confidence</dt><dd><ConfidenceMeter value={incident.confidence} /></dd></div>
            <div><dt>Estimated cost</dt><dd className="mono">{formatUsd(incident.estimated_ai_cost_usd)}</dd></div>
          </dl>
        </aside>
      </div>

      {dialog ? (
        <ApprovalDialog
          incident={incident}
          mode={dialog}
          busy={busy !== null}
          onCancel={() => setDialog(null)}
          onConfirm={() => {
            const mode = dialog;
            void act(mode, async () => {
              if (!approvalId) throw new ApiError(409, "No approval_id is attached to this incident.", null);
              if (mode === "approve") await approveIncident(incident.incident_id, approvalId);
              else await rejectIncident(incident.incident_id, approvalId);
            });
          }}
        />
      ) : null}
    </section>
  );
}

function HeaderActions(props: {
  status: Incident["status"];
  busy: string | null;
  canDecide: boolean;
  onInvestigate: () => void;
  onReview: () => void;
  onApprove: () => void;
  onReject: () => void;
  onExecute: () => void;
  onTrace: () => void;
}) {
  const { status, busy } = props;
  if (status === "DETECTED" || status === "QUEUED") {
    return <button type="button" data-testid="investigate" disabled={busy !== null} onClick={props.onInvestigate}>{busy === "investigate" ? "Investigating…" : "Investigate"}</button>;
  }
  if (status === "INVESTIGATING") return <button type="button" disabled>Investigating…</button>;
  if (status === "DIAGNOSED" || status === "REMEDIATION_PROPOSED") {
    return <button type="button" onClick={props.onReview}>Review action</button>;
  }
  if (status === "AWAITING_APPROVAL") {
    return (
      <div className="row-actions">
        <button type="button" data-testid="open-approve" disabled={!props.canDecide || busy !== null} onClick={props.onApprove}>Approve</button>
        <button type="button" className="secondary" data-testid="open-reject" disabled={!props.canDecide || busy !== null} onClick={props.onReject}>Reject</button>
        <button type="button" className="secondary" data-testid="execute-early" disabled={busy !== null} onClick={props.onExecute}>Execute remediation</button>
      </div>
    );
  }
  if (status === "APPROVED") {
    return <button type="button" data-testid="execute" disabled={busy !== null} onClick={props.onExecute}>{busy === "execute" ? "Executing…" : "Execute remediation"}</button>;
  }
  if (status === "RESOLVED") {
    return <button type="button" className="secondary" onClick={props.onTrace}>Open trace</button>;
  }
  return null;
}

function Overview({ incident }: { incident: Incident }) {
  return (
    <div className="panel stack">
      <h2>Overview</h2>
      <p>{incident.diagnosis?.summary || "Investigation has not produced a diagnosis yet."}</p>
      <p><strong>Probable cause.</strong> {incident.diagnosis?.probable_cause || "—"}</p>
      <p><strong>Recommended action.</strong> {incident.recommended_action || "—"}</p>
      <p className="muted">Estimated AI cost {formatUsd(incident.estimated_ai_cost_usd)}</p>
    </div>
  );
}

function Timeline({ events, denial }: { events: IncidentEvent[]; denial: DenialNotice | null }) {
  const ordered = useMemo(() => [...events].sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp)), [events]);
  return (
    <div className="panel">
      <h2>Timeline</h2>
      <div className="timeline">
        {ordered.length === 0 && !denial ? <p className="muted">No events yet.</p> : null}
        {ordered.map((event) => (
          <article key={event.event_id} className="event">
            <time className="muted">{formatTime(event.timestamp)}</time>
            <span className="mono">{event.actor}</span>
            <div>
              <strong>{event.event_type}</strong>
              {event.from_status || event.to_status ? (
                <div className="muted">{event.from_status || "—"} → {event.to_status || "—"}</div>
              ) : null}
            </div>
          </article>
        ))}
        {denial ? (
          <article className="event denied" data-testid="denied-event">
            <time className="muted">{formatTime(denial.at)}</time>
            <span className="mono">human:demo</span>
            <div><strong>Denied — missing valid approval</strong><div className="muted">{denial.message}</div></div>
          </article>
        ) : null}
      </div>
    </div>
  );
}

function Investigation({ events, incident }: { events: IncidentEvent[]; incident: Incident }) {
  const tools = events.filter((event) => event.event_type === "TOOL_CALLED");
  return (
    <div className="stack">
      {tools.length === 0 ? <p className="muted">No tool calls yet. Start an investigation to record them.</p> : null}
      {tools.map((event, index) => {
        const payload = event.payload;
        const name = String(payload.tool || "tool");
        return (
          <article key={event.event_id} className="tool">
            <header>
              <span className="chip st-INVESTIGATING">{name}</span>
              <span className="muted">{typeof payload.latency_ms === "number" ? `${payload.latency_ms} ms` : "—"} · step {index + 1}</span>
            </header>
            <p className="muted">{payload.ok === false ? String(payload.error || "Tool failed") : "Call recorded"}</p>
          </article>
        );
      })}
      {incident.diagnosis ? (
        <article className="kind inference">
          <div className="label">Inference</div>
          <p>{incident.diagnosis.probable_cause}</p>
          <ConfidenceMeter value={incident.diagnosis.confidence} />
        </article>
      ) : null}
    </div>
  );
}

function EvidencePanel({ evidence, events }: { evidence: Evidence[]; events: IncidentEvent[] }) {
  const tools = new Set(events.filter((event) => event.event_type === "TOOL_CALLED").map((event) => String(event.payload.tool || "")));
  if (evidence.length === 0) return <p className="muted">No evidence rows yet.</p>;
  return (
    <div className="stack">
      {evidence.map((item) => (
        <article key={item.evidence_id} className={`kind ${item.kind === "inference" ? "inference" : ""}`}>
          <div className="label">{item.kind.replaceAll("_", " ")}</div>
          <p>{item.summary}</p>
          <p className="muted mono">source {item.source}{tools.size ? ` · tools ${[...tools].join(", ")}` : ""}</p>
        </article>
      ))}
    </div>
  );
}

function Knowledge({ incident }: { incident: Incident }) {
  const sources = incident.diagnosis?.retrieved_sources ?? [];
  const retrieved = (incident.diagnosis?.evidence ?? []).filter((item) => item.kind === "retrieved_guidance");
  if (sources.length === 0 && retrieved.length === 0) {
    return <p className="muted">No retrieved source IDs yet.</p>;
  }
  return (
    <div className="stack">
      {sources.map((source) => (
        <article key={source} className="kind">
          <div className="label">Retrieved guidance</div>
          <p>Runbook or ADR cited by the investigation.</p>
          <CopyId value={source} label="source id" />
        </article>
      ))}
      {retrieved.map((item) => (
        <article key={item.evidence_id} className="kind">
          <div className="label">Retrieved guidance</div>
          <p>{item.summary}</p>
          <CopyId value={item.source} label="source id" />
        </article>
      ))}
    </div>
  );
}

function Action({ incident }: { incident: Incident }) {
  const proposal = incident.proposal;
  return (
    <div className="panel stack">
      <h2>Recommended action</h2>
      <p>{proposal?.action || incident.recommended_action || "No action has been proposed."}</p>
      {proposal ? <p className="muted">{proposal.rationale}</p> : null}
      <p className="muted">
        Effect: {proposal?.requires_approval === false ? "no write" : "SAFE_WRITE"}. Destructive actions stay disabled.
      </p>
    </div>
  );
}

function ApprovalPanel({
  incident,
  onApprove,
  onReject,
}: {
  incident: Incident;
  onApprove: () => void;
  onReject: () => void;
}) {
  const approval = incident.approval;
  return (
    <div className="panel stack">
      <h2>Approval</h2>
      {approval ? (
        <>
          <p>Status <strong>{approval.status}</strong> · actor <span className="mono">{approval.actor}</span></p>
          <p className="mono">approval_id <CopyId value={approval.approval_id} label="approval_id" /></p>
          <p className="muted">Expires {formatTime(approval.expires_at)}</p>
        </>
      ) : (
        <p className="muted">No approval record yet.</p>
      )}
      {incident.status === "AWAITING_APPROVAL" ? (
        <div className="row-actions">
          <button type="button" onClick={onApprove}>Approve</button>
          <button type="button" className="secondary" onClick={onReject}>Reject</button>
        </div>
      ) : null}
    </div>
  );
}

function Execution({
  incident,
  onAttempt,
  busy,
}: {
  incident: Incident;
  onAttempt: () => void;
  busy: boolean;
}) {
  const granted = incident.status === "APPROVED" || incident.status === "RESOLVED" || incident.status === "REMEDIATING" || incident.status === "FAILED";
  return (
    <div className="panel stack">
      <h2>Execution</h2>
      <p>{incident.active_remediation_id ? `Remediation ${incident.active_remediation_id}` : "No remediation has executed."}</p>
      <p className="muted">One active remediation. A second attempt is rejected as a duplicate.</p>
      {incident.status === "RESOLVED" ? <p>The incident is RESOLVED.</p> : null}
      {!granted && incident.status !== "REJECTED" ? (
        <button type="button" className="secondary" data-testid="execute-panel" disabled={busy} onClick={onAttempt}>
          {busy ? "Executing…" : "Attempt remediation"}
        </button>
      ) : null}
      {incident.status === "APPROVED" ? (
        <button type="button" disabled={busy} onClick={onAttempt}>{busy ? "Executing…" : "Execute remediation"}</button>
      ) : null}
    </div>
  );
}

function CostPanel({ incident, runs }: { incident: Incident; runs: AgentRunsResponse | null }) {
  const latest = runs?.runs.at(-1);
  return (
    <div className="panel stack">
      <h2>Cost</h2>
      <div className="kpis">
        <div className="kpi"><span>Estimated USD</span><strong>{formatUsd(runs?.EstimatedCostPerIncident ?? incident.estimated_ai_cost_usd)}</strong></div>
        <div className="kpi"><span>Tokens</span><strong>{runs?.TokensPerIncident ?? (latest ? latest.input_tokens + latest.output_tokens : 0)}</strong></div>
        <div className="kpi"><span>Tool calls</span><strong>{runs?.ToolCallsPerIncident ?? latest?.tool_calls ?? 0}</strong></div>
      </div>
      {latest ? (
        <p className="muted">Input {latest.input_tokens} · output {latest.output_tokens} · RAG calls {latest.rag_calls} · runtime {latest.runtime_ms} ms</p>
      ) : (
        <p className="muted">No agent run yet.</p>
      )}
      <a className="button secondary" href="/evaluations">Open evaluations</a>
    </div>
  );
}

function TracePanel({ runs }: { runs: AgentRunsResponse | null }) {
  const spans = runs?.trace.spans ?? [];
  return (
    <div className="panel">
      <h2>Trace</h2>
      {runs?.runs[0] ? <p className="mono">agent_run_id <CopyId value={runs.runs[0].agent_run_id} label="agent_run_id" /></p> : null}
      {spans.length === 0 ? <p className="muted">No spans recorded for this incident.</p> : <SpanTree spans={spans} />}
    </div>
  );
}

function SpanTree({ spans }: { spans: TraceSpan[] }) {
  return (
    <div className="span-tree">
      {spans.map((span) => (
        <div key={span.span_id} className="span-node">
          <span className="mono">{span.name}</span>
          {span.children.length > 0 ? <SpanTree spans={span.children} /> : null}
        </div>
      ))}
    </div>
  );
}

function ApprovalDialog({
  incident,
  mode,
  busy,
  onCancel,
  onConfirm,
}: {
  incident: Incident;
  mode: "approve" | "reject";
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const approval = incident.approval;
  return (
    <div className="overlay" role="presentation">
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="approval-title" data-testid="approval-dialog">
        <h2 id="approval-title">{mode === "approve" ? "Approve remediation" : "Reject remediation"}</h2>
        <p><strong>Action.</strong> {incident.proposal?.action || incident.recommended_action || "—"}</p>
        <p><strong>Why.</strong> {incident.diagnosis?.probable_cause || "—"} · confidence {incident.confidence ?? "—"}</p>
        <p><strong>Effect.</strong> SAFE_WRITE. Destructive actions are disabled.</p>
        <p><strong>Expires.</strong> {approval ? formatTime(approval.expires_at) : "—"} · <span className="mono">{approval?.approval_id || "no approval_id"}</span></p>
        <div className="row-actions">
          {mode === "approve" ? (
            <button type="button" data-testid="confirm-approve" disabled={busy} onClick={onConfirm}>{busy ? "Saving…" : "Approve"}</button>
          ) : (
            <button type="button" className="danger" data-testid="confirm-reject" disabled={busy} onClick={onConfirm}>{busy ? "Saving…" : "Reject"}</button>
          )}
          <button type="button" className="secondary" onClick={onCancel}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
