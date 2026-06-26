import type { BadgeTone } from "@/components/ui/badge";
import type { LeadScoreBand, LeadStatus, SearchJobStatus } from "@/types/api";

export function formatDate(value: string | null | undefined, locale?: string) {
  if (!value) {
    return "Not yet";
  }
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatRelativeTime(
  value: string | null | undefined,
  locale?: string,
  now = new Date(),
) {
  if (!value) {
    return "Not yet";
  }
  const date = new Date(value);
  const diffSeconds = Math.round((date.getTime() - now.getTime()) / 1000);
  const absoluteSeconds = Math.abs(diffSeconds);
  const formatter = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });

  if (absoluteSeconds < 60) {
    return formatter.format(diffSeconds, "second");
  }
  const diffMinutes = Math.round(diffSeconds / 60);
  if (Math.abs(diffMinutes) < 60) {
    return formatter.format(diffMinutes, "minute");
  }
  const diffHours = Math.round(diffMinutes / 60);
  if (Math.abs(diffHours) < 24) {
    return formatter.format(diffHours, "hour");
  }
  const diffDays = Math.round(diffHours / 24);
  if (Math.abs(diffDays) < 30) {
    return formatter.format(diffDays, "day");
  }
  return formatDate(value, locale);
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
  if (band === "high" || band === "hot_lead") {
    return "success";
  }
  if (
    band === "medium" ||
    band === "low" ||
    band === "warm_lead" ||
    band === "research_more"
  ) {
    return "accent";
  }
  if (band === "do_not_contact") {
    return "danger";
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
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char: string) => char.toUpperCase());
}
