"use client";

import { useState } from "react";
import type { IncidentStatus, Severity } from "@/lib/types";
import { confidenceTone, formatConfidence, truncateId } from "@/lib/format";

const ACTIVE = new Set<IncidentStatus>(["INVESTIGATING", "REMEDIATING"]);

export function StatusChip({ status }: { status: IncidentStatus }) {
  return (
    <span className={`chip st-${status} ${ACTIVE.has(status) ? "pulse" : ""}`}>{status}</span>
  );
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <span className={`badge sev-${severity}`}>{severity}</span>;
}

export function ConfidenceMeter({ value }: { value: number | null | undefined }) {
  const tone = confidenceTone(value);
  const width = value == null ? 0 : Math.max(0, Math.min(100, value * 100));
  return (
    <span className="inline" title={formatConfidence(value)}>
      <span className="meter" aria-hidden>
        <span className={`tone-${tone}`} style={{ width: `${width}%` }} />
      </span>
      <span className={`tone-${tone}`} style={{ background: "transparent" }}>
        {formatConfidence(value)}
      </span>
    </span>
  );
}

export function CopyId({ value, label, max = 18 }: { value: string; label?: string; max?: number }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="copy mono"
      aria-label={label ? `Copy ${label}` : `Copy ${value}`}
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        void navigator.clipboard.writeText(value).then(() => {
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1200);
        });
      }}
    >
      {copied ? "Copied" : truncateId(value, max)}
    </button>
  );
}

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: React.ReactNode;
}) {
  return (
    <section className="empty">
      <div className="mark" aria-hidden>
        ∅
      </div>
      <h2>{title}</h2>
      <p className="lede">{body}</p>
      {action ? <div style={{ marginTop: 16 }}>{action}</div> : null}
    </section>
  );
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="banner error" role="alert">
      <div className="row-actions" style={{ justifyContent: "space-between" }}>
        <span>{message}</span>
        {onRetry ? (
          <button type="button" className="secondary" onClick={onRetry}>
            Retry
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function Loading({ label }: { label: string }) {
  return <p className="muted">{label}</p>;
}
