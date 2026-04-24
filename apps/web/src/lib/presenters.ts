import type { BadgeTone } from "@/components/ui/badge";
import type { LeadScoreBand, LeadStatus, SearchJobStatus } from "@/types/api";

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

export function bandTone(band: LeadScoreBand | null | undefined): BadgeTone {
  if (band === "high") {
    return "success";
  }
  if (band === "medium" || band === "low") {
    return "accent";
  }
  return "neutral";
}

export function statusTone(status: LeadStatus): BadgeTone {
  if (status === "qualified" || status === "interested" || status === "won") {
    return "success";
  }
  if (status === "contacted" || status === "reviewed") {
    return "accent";
  }
  if (status === "lost" || status === "archived") {
    return "danger";
  }
  return "neutral";
}

export function searchJobTone(status: SearchJobStatus): BadgeTone {
  if (status === "completed") {
    return "success";
  }
  if (status === "partially_completed") {
    return "warning";
  }
  if (status === "failed") {
    return "danger";
  }
  return "accent";
}

export function titleCaseLabel(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char: string) => char.toUpperCase());
}
