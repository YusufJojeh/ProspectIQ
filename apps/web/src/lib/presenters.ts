import type { LeadScoreBand, LeadStatus } from "@/types/api";

export function formatDate(value: string | null | undefined) {
  if (!value) {
    return "Not yet";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "N/A";
  }
  return `${Math.round(value * 100)}%`;
}

export function formatScore(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "Unscored";
  }
  return `${Math.round(value)}/100`;
}

export function bandTone(band: LeadScoreBand | null | undefined): "neutral" | "accent" | "warning" {
  if (band === "high") {
    return "warning";
  }
  if (band === "medium" || band === "low") {
    return "accent";
  }
  return "neutral";
}

export function statusTone(status: LeadStatus): "neutral" | "accent" | "warning" {
  if (status === "qualified" || status === "interested" || status === "won") {
    return "warning";
  }
  if (status === "contacted" || status === "reviewed") {
    return "accent";
  }
  return "neutral";
}

export function titleCaseLabel(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char: string) => char.toUpperCase());
}
