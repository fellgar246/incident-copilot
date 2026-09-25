import type { IncidentStatus } from "./types";
import { HAPPY_PATH } from "./types";

export function formatUsd(value: number | null | undefined): string {
  const amount = value ?? 0;
  if (amount === 0) return "$0.00";
  if (amount < 0.01) return `$${amount.toFixed(6)}`;
  return `$${amount.toFixed(2)}`;
}

export function formatConfidence(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${Math.round(value * 100)}%`;
}

export function confidenceTone(value: number | null | undefined): "good" | "warn" | "bad" | "muted" {
  if (value == null || Number.isNaN(value)) return "muted";
  if (value >= 0.8) return "good";
  if (value >= 0.5) return "warn";
  return "bad";
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function truncateId(value: string, head = 12): string {
  if (value.length <= head + 4) return value;
  return `${value.slice(0, head)}…`;
}

export function lifecycleIndex(status: IncidentStatus): number {
  if (status === "REJECTED") return HAPPY_PATH.indexOf("AWAITING_APPROVAL");
  if (status === "FAILED") return HAPPY_PATH.indexOf("REMEDIATING");
  const index = HAPPY_PATH.indexOf(status);
  return index === -1 ? 0 : index;
}

export function probableCause(incident: {
  diagnosis: { probable_cause: string } | null;
}): string {
  return incident.diagnosis?.probable_cause ?? "—";
}

const DENIAL_PREFIX = "aic-denial:";

export interface DenialNotice {
  at: string;
  message: string;
}

export function readDenial(incidentId: string): DenialNotice | null {
  if (typeof sessionStorage === "undefined") return null;
  const raw = sessionStorage.getItem(`${DENIAL_PREFIX}${incidentId}`);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as DenialNotice;
    if (parsed && typeof parsed.message === "string") return parsed;
  } catch {
    return null;
  }
  return null;
}

export function writeDenial(incidentId: string, message: string): DenialNotice {
  const notice: DenialNotice = { at: new Date().toISOString(), message };
  sessionStorage.setItem(`${DENIAL_PREFIX}${incidentId}`, JSON.stringify(notice));
  return notice;
}
