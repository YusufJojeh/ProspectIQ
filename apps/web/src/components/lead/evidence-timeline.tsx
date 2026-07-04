import {
  Database,
  Globe,
  Hash,
  MapPin,
  Navigation,
  Phone,
  Search,
  ShieldCheck,
  Star,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { formatDate, titleCaseLabel } from "@/lib/presenters";
import type { LeadEvidenceItem } from "@/types/api";

const evidenceMeta: Record<
  string,
  {
    icon: React.ComponentType<{ className?: string }>;
    tone: "accent" | "success" | "warning" | "neutral";
  }
> = {
  listing: { icon: MapPin, tone: "accent" },
  review: { icon: Star, tone: "warning" },
  web: { icon: Globe, tone: "success" },
  website: { icon: Globe, tone: "success" },
  search: { icon: Search, tone: "accent" },
};

export function LeadEvidenceTimeline({
  items,
}: {
  items: LeadEvidenceItem[];
}) {
  const { t } = useTranslation();
  const displayItems = dedupeEvidenceItems(items);
  const summary = buildVisibleSummary(displayItems);
  const hiddenCount = items.length - displayItems.length;

  return (
    <section className="overflow-hidden rounded-[1.5rem] border border-border bg-card/95 shadow-sm">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-border bg-gradient-to-br from-[oklch(var(--signal)/0.12)] via-card to-[oklch(var(--evidence)/0.08)] px-4 py-4">
        <div>
          <h2 className="text-base font-semibold">
            {t("leadDetail.evidenceTimeline")}
          </h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
            {t("leadDetail.evidenceTimelineDescription")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {summary.slice(0, 4).map((item) => (
            <Badge key={item.label} tone="evidence">
              {item.label} {item.count}
            </Badge>
          ))}
          {hiddenCount > 0 ? (
            <Badge tone="warning">
              {t("leadDetail.evidenceDuplicatesCollapsed", {
                count: hiddenCount,
                defaultValue: "{{count}} older duplicates hidden",
              })}
            </Badge>
          ) : null}
        </div>
      </header>

      <div className="space-y-3 p-4">
        {displayItems.map((item) => {
          const meta = evidenceMeta[item.source_type] ?? {
            icon: Database,
            tone: "neutral" as const,
          };
          const Icon = meta.icon;
          const evidenceFacts = buildEvidenceFacts(item);
          const providerFields = getStringArrayFact(
            item.facts,
            "provider_fields_present",
          );
          return (
            <article
              key={item.display_key}
              className="overflow-hidden rounded-2xl border border-border bg-background/80 shadow-sm transition-colors hover:border-[oklch(var(--signal)/0.35)]"
            >
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border bg-muted/20 p-4">
                <div className="flex min-w-0 items-start gap-3">
                  <div className="rounded-2xl border border-[oklch(var(--signal)/0.25)] bg-[oklch(var(--signal)/0.1)] p-2.5">
                    <Icon className="size-4 text-[oklch(var(--signal))]" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium">
                        {titleCaseLabel(item.source_type.replace(/_/g, " "))}
                      </p>
                      <Badge tone={meta.tone}>
                        {t("leadDetail.confidencePct", {
                          pct: Math.round(item.confidence * 100),
                        })}
                      </Badge>
                      <Badge tone="neutral">
                        {t("leadDetail.completenessPct", {
                          pct: Math.round(item.completeness * 100),
                        })}
                      </Badge>
                      {item.duplicate_count > 0 ? (
                        <Badge tone="warning">
                          {t("leadDetail.evidenceOlderRuns", {
                            count: item.duplicate_count,
                            defaultValue: "+{{count}} older runs",
                          })}
                        </Badge>
                      ) : null}
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {item.company_name} -{" "}
                      {item.address ??
                        item.city ??
                        t("leadDetail.noAddressCaptured")}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      <span>{item.request_mode}</span>
                      <span>{item.provider_status}</span>
                      <span>{formatDate(item.created_at)}</span>
                    </div>
                  </div>
                </div>
                <div className="rounded-full border border-[oklch(var(--evidence)/0.25)] bg-[oklch(var(--evidence)/0.1)] p-2 text-[oklch(var(--evidence))]">
                  <ShieldCheck className="size-4" />
                </div>
              </div>

              <div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-4">
                {evidenceFacts.map((fact) => (
                  <EvidenceFact key={fact.label} {...fact} />
                ))}
              </div>

              {providerFields.length > 0 ? (
                <div className="border-t border-border px-4 py-3">
                  <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
                    {t("leadDetail.providerFieldsPresent", {
                      defaultValue: "Provider fields present",
                    })}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {providerFields.slice(0, 12).map((field) => (
                      <Badge key={field} tone="neutral">
                        {titleCaseLabel(field)}
                      </Badge>
                    ))}
                  </div>
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}

type DisplayEvidenceItem = LeadEvidenceItem & {
  display_key: string;
  duplicate_count: number;
};

function dedupeEvidenceItems(items: LeadEvidenceItem[]): DisplayEvidenceItem[] {
  const byKey = new Map<string, DisplayEvidenceItem>();
  const sortedItems = [...items].sort(
    (a, b) =>
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  for (const item of sortedItems) {
    const key = getEvidenceIdentityKey(item);
    const existing = byKey.get(key);
    if (existing) {
      existing.duplicate_count += 1;
      continue;
    }
    byKey.set(key, {
      ...item,
      display_key: key,
      duplicate_count: 0,
    });
  }

  return [...byKey.values()];
}

function buildVisibleSummary(items: DisplayEvidenceItem[]) {
  return items.reduce<Array<{ label: string; count: number }>>(
    (summary, item) => {
      const label = titleCaseLabel(item.source_type.replace(/_/g, " "));
      const existing = summary.find((entry) => entry.label === label);
      if (existing) {
        existing.count += 1;
      } else {
        summary.push({ label, count: 1 });
      }
      return summary;
    },
    [],
  );
}

function getEvidenceIdentityKey(item: LeadEvidenceItem) {
  return [
    item.source_type,
    item.place_id?.trim().toLowerCase() ?? "",
    item.data_cid?.trim().toLowerCase() ?? "",
    item.data_id?.trim().toLowerCase() ?? "",
    (item.website_domain ?? item.website_url ?? "").trim().toLowerCase(),
    item.phone?.trim().toLowerCase() ?? "",
    typeof item.lat === "number" && typeof item.lng === "number"
      ? `${item.lat.toFixed(6)},${item.lng.toFixed(6)}`
      : "",
  ].join("|");
}

function EvidenceFact({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="min-w-0 rounded-xl border border-border bg-card/80 p-3">
      <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
        <Icon className="size-3.5 shrink-0" />
        <span>{label}</span>
      </div>
      <p className="mt-2 break-words text-sm font-medium leading-6 text-foreground">
        {value}
      </p>
    </div>
  );
}

function buildEvidenceFacts(item: LeadEvidenceItem) {
  const coordinates = getCoordinates(item);
  const sourceIds = getSourceIds(item);

  return [
    {
      icon: MapPin,
      label: "Address",
      value: item.address ?? item.city ?? "Not captured",
    },
    {
      icon: Phone,
      label: "Phone",
      value: item.phone ?? "Not captured",
    },
    {
      icon: Globe,
      label: "Website",
      value: item.website_domain ?? item.website_url ?? "Not captured",
    },
    {
      icon: Star,
      label: "Reviews",
      value:
        item.rating !== null || item.review_count > 0
          ? `${item.rating ?? "N/A"} rating / ${item.review_count} reviews`
          : "Not captured",
    },
    {
      icon: Database,
      label: "Category",
      value:
        item.category ?? getStringFact(item.facts, "category") ?? "Not captured",
    },
    {
      icon: Navigation,
      label: "Coordinates",
      value: coordinates ?? "Not captured",
    },
    {
      icon: Hash,
      label: "Source IDs",
      value: sourceIds ?? "Not captured",
    },
    {
      icon: Search,
      label: "Provider",
      value:
        [
          getStringFact(item.facts, "source_engine"),
          getStringFact(item.facts, "adapter_name"),
          getStringFact(item.facts, "query_variant"),
        ]
          .filter(Boolean)
          .join(" / ") || titleCaseLabel(item.request_mode),
    },
  ];
}

function getCoordinates(item: LeadEvidenceItem) {
  if (typeof item.lat === "number" && typeof item.lng === "number") {
    return `${item.lat.toFixed(6)}, ${item.lng.toFixed(6)}`;
  }

  const coordinates = item.facts.coordinates;
  if (
    coordinates &&
    typeof coordinates === "object" &&
    "lat" in coordinates &&
    "lng" in coordinates
  ) {
    const lat = Number(coordinates.lat);
    const lng = Number(coordinates.lng);
    if (Number.isFinite(lat) && Number.isFinite(lng)) {
      return `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
    }
  }

  return null;
}

function getSourceIds(item: LeadEvidenceItem) {
  const ids = [
    item.place_id ? `Place ${item.place_id}` : null,
    item.data_cid ? `CID ${item.data_cid}` : null,
    item.data_id ? `Data ${item.data_id}` : null,
  ].filter(Boolean);

  if (ids.length > 0) {
    return ids.join(" / ");
  }

  const sourceIds = item.facts.source_ids;
  if (!sourceIds || typeof sourceIds !== "object") {
    return null;
  }

  return Object.entries(sourceIds)
    .filter(([, value]) => typeof value === "string" && value.length > 0)
    .map(([key, value]) => `${titleCaseLabel(key)} ${value}`)
    .join(" / ");
}

function getStringFact(facts: Record<string, unknown>, key: string) {
  const value = facts[key];
  return typeof value === "string" && value.trim().length > 0
    ? value.trim()
    : null;
}

function getStringArrayFact(facts: Record<string, unknown>, key: string) {
  const value = facts[key];
  return Array.isArray(value)
    ? value.filter(
        (item): item is string =>
          typeof item === "string" && item.trim().length > 0,
      )
    : [];
}
