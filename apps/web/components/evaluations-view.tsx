"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, getEvaluations } from "@/lib/api";
import { formatUsd } from "@/lib/format";
import { EVALUATION_METRICS } from "@/lib/product-surface";
import type { EvaluationSummary } from "@/lib/types";
import { ErrorBanner, Loading } from "./ui";

const LABELS: Record<(typeof EVALUATION_METRICS)[number], string> = {
  evaluation_pass_rate: "Pass rate",
  diagnosis_accuracy: "Diagnosis accuracy",
  groundedness: "Groundedness",
  unsafe_action_count: "Unsafe actions",
  avg_tool_calls: "Avg tool calls",
  avg_estimated_cost: "Avg estimated cost",
};

function display(metric: (typeof EVALUATION_METRICS)[number], summary: EvaluationSummary): string {
  const value = summary[metric];
  if (typeof value !== "number") return "—";
  if (metric === "avg_estimated_cost") return formatUsd(value);
  if (metric === "unsafe_action_count" || metric === "avg_tool_calls") return String(value);
  return `${Math.round(value * 1000) / 10}%`;
}

export function EvaluationsView() {
  const [summary, setSummary] = useState<EvaluationSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setSummary(await getEvaluations());
    } catch (cause) {
      setSummary(null);
      setError(cause instanceof ApiError ? cause.message : "Could not load evaluations.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) return <ErrorBanner message={error} onRetry={() => void load()} />;
  if (!summary) return <Loading label="Loading evaluations…" />;

  const gates = summary.gates ?? {};
  const gateRows = Object.entries(gates);

  return (
    <section className="stack">
      <header>
        <h1>Evaluations</h1>
        <p className="lede">
          Latest offline run · profile {summary.profile} · {summary.case_count} cases
          {summary.passed ? " · passed" : ""}
        </p>
      </header>
      <div className="kpis" data-testid="eval-kpis">
        {EVALUATION_METRICS.map((metric) => {
          const highlight =
            (metric === "unsafe_action_count" && summary.unsafe_action_count > 0) ||
            (metric === "groundedness" && summary.groundedness < 0.8);
          return (
            <div key={metric} className={`kpi ${highlight ? "bad" : ""}`}>
              <span>{LABELS[metric]}</span>
              <strong>{display(metric, summary)}</strong>
            </div>
          );
        })}
      </div>
      {summary.case_count === 0 ? (
        <section className="empty">
          <h2>No evaluation run yet</h2>
          <p className="lede">Run make eval to write the latest summary the API serves.</p>
        </section>
      ) : null}
      <div className="panel">
        <h2>Gates</h2>
        {gateRows.length === 0 ? <p className="muted">The summary has no per-gate rows.</p> : null}
        {gateRows.length > 0 ? (
          <table>
            <thead>
              <tr><th>Gate</th><th>Result</th></tr>
            </thead>
            <tbody>
              {gateRows.map(([name, passed]) => (
                <tr key={name}>
                  <td className="mono">{name}</td>
                  <td>{passed ? "pass" : "fail"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
        {summary.cohorts?.length ? <p className="muted">Cohorts {summary.cohorts.join(", ")}</p> : null}
      </div>
    </section>
  );
}
