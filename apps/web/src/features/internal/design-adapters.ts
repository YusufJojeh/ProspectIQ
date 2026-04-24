import { bandFromScore } from "@/components/brand/badges";
import type {
  AuditLogResponse,
  LeadActivityEntry,
  LeadEvidenceItem,
  LeadResponse,
  LeadScoreBreakdownResponse,
  SearchJobResponse,
} from "@/types/api";

const SCORE_COLORS = {
  A: "oklch(var(--score-a))",
  B: "oklch(var(--score-b))",
  C: "oklch(var(--score-c))",
  D: "oklch(var(--score-d))",
  E: "oklch(var(--score-e))",
} as const;

export function scoreBandLetter(score: number | null | undefined) {
  return bandFromScore(score ?? 0);
}

export function buildScoreDistribution(leads: LeadResponse[]) {
  const counts = { A: 0, B: 0, C: 0, D: 0, E: 0 };
  for (const lead of leads) {
    counts[scoreBandLetter(lead.latest_score)] += 1;
  }

  return Object.entries(counts).map(([band, count]) => ({
    band,
    count,
    fill: SCORE_COLORS[band as keyof typeof SCORE_COLORS],
  }));
}

export function buildJobThroughputSeries(jobs: SearchJobResponse[]) {
  const labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const buckets = labels.map((label) => ({ label, discovered: 0, qualified: 0 }));

  for (const job of jobs) {
    const date = new Date(job.finished_at ?? job.started_at ?? job.queued_at);
    const bucket = buckets[date.getUTCDay() === 0 ? 6 : date.getUTCDay() - 1];
    bucket.discovered += job.candidates_found;
    bucket.qualified += job.leads_upserted;
  }

  return buckets;
}

export function buildCityCoverage(leads: LeadResponse[]) {
  return Object.entries(
    leads.reduce<Record<string, number>>((acc, lead) => {
      const key = lead.city?.trim() || "Unknown";
      acc[key] = (acc[key] ?? 0) + 1;
      return acc;
    }, {}),
  )
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([city, count]) => ({ city, count }));
}

export function buildLeadHealth(lead: LeadResponse) {
  return [
    {
      label: "Data confidence",
      value: Math.round(lead.data_confidence * 100),
      helper:
        lead.data_confidence >= 0.8
          ? "Evidence consistency is high across stored facts."
          : "This record may benefit from another refresh pass.",
    },
    {
      label: "Data completeness",
      value: Math.round(lead.data_completeness * 100),
      helper:
        lead.data_completeness >= 0.8
          ? "Core contact and location fields are mostly complete."
          : "Some fields are still missing from normalized evidence.",
    },
    {
      label: "Website readiness",
      value: lead.has_website ? 100 : 0,
      helper: lead.has_website ? "A website is available for outbound preparation." : "No website is stored yet.",
    },
  ];
}

export function buildBreakdownSummary(breakdown: LeadScoreBreakdownResponse | null | undefined) {
  if (!breakdown) {
    return [];
  }

  return breakdown.breakdown.map((item) => ({
    ...item,
    percent: Math.max(0, Math.min(100, Math.round((item.contribution / Math.max(breakdown.total_score, 1)) * 100))),
  }));
}

export function buildEvidenceSummary(items: LeadEvidenceItem[]) {
  const grouped = items.reduce<Record<string, number>>((acc, item) => {
    const key = item.source_type.replace(/_/g, " ");
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});

  return Object.entries(grouped)
    .sort((a, b) => b[1] - a[1])
    .map(([label, count]) => ({ label, count }));
}

export function mergeActivityTimeline(
  activity: LeadActivityEntry[],
  auditLogs: AuditLogResponse[] = [],
) {
  const activityItems = activity.map((item) => ({
    id: item.entry_id,
    source: item.entry_type === "status_change" ? "workflow" : "note",
    createdAt: item.created_at,
    title: item.entry_type === "status_change" ? "Status updated" : "Internal note",
    detail:
      item.entry_type === "status_change"
        ? `${item.from_status ?? "initial"} to ${item.to_status ?? "unknown"}`
        : item.note ?? "No note body stored.",
    actor: item.actor_full_name ?? item.actor_user_public_id ?? "System",
  }));

  const auditItems = auditLogs.map((item) => ({
    id: item.public_id,
    source: "audit",
    createdAt: item.created_at,
    title: item.event_name,
    detail: item.details,
    actor: item.actor_user_public_id ?? "system",
  }));

  return [...activityItems, ...auditItems].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
  );
}
