"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, getCosts } from "@/lib/api";
import { formatUsd } from "@/lib/format";
import { EFFECTIVE_LIMITS, TARGET_MONTHLY_COST_USD } from "@/lib/limits";
import type { CostMetrics } from "@/lib/types";
import { ErrorBanner, Loading } from "./ui";

export function CostsView() {
  const [costs, setCosts] = useState<CostMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setCosts(await getCosts());
    } catch (cause) {
      setCosts(null);
      setError(cause instanceof ApiError ? cause.message : "Could not load cost metrics.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const spent = costs?.series.estimated_cost ?? 0;
  const ratio = Math.min(100, (spent / TARGET_MONTHLY_COST_USD) * 100);

  return (
    <section className="stack">
      <header>
        <h1>Costs</h1>
        <p className="lede">
          Design target ${TARGET_MONTHLY_COST_USD.toFixed(2)} / month. This is not a billing guarantee.
          Limits cannot be raised from this session.
        </p>
      </header>
      {error ? <ErrorBanner message={error} onRetry={() => void load()} /> : null}
      {!costs && !error ? <Loading label="Loading cost metrics…" /> : null}
      <div className="panel stack">
        <h2>Estimated spend vs target</h2>
        <p>
          You&apos;ve spent <strong>{formatUsd(spent)}</strong> · {formatUsd(Math.max(0, TARGET_MONTHLY_COST_USD - spent))} remaining of the design target
        </p>
        <div className="bar" aria-hidden>
          <span style={{ width: `${ratio}%` }} />
        </div>
        <p className="muted">
          {costs ? `${costs.series.incidents_total} incidents · ${costs.series.tool_calls} tool calls · ${costs.series.input_tokens + costs.series.output_tokens} tokens` : "Spend appears after the API responds."}
        </p>
      </div>
      <div className="panel">
        <h2>Effective limits</h2>
        <table>
          <thead>
            <tr><th>Limit</th><th>Value</th></tr>
          </thead>
          <tbody>
            {EFFECTIVE_LIMITS.map((limit) => (
              <tr key={limit.name}>
                <td className="mono">{limit.name}</td>
                <td>{limit.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
