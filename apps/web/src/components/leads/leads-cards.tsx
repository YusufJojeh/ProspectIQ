import { ArrowUpRight, Globe, MapPin, Star } from "lucide-react";
import { Link } from "react-router-dom";
import { appPaths } from "@/app/paths";
import { ScoreRing } from "@/components/brand/score-ring";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { bandTone, formatScore, statusTone, titleCaseLabel } from "@/lib/presenters";
import type { LeadResponse } from "@/types/api";

export function LeadsCards({
  leads,
  selectedIds,
  onToggleSelect,
}: {
  leads: LeadResponse[];
  selectedIds: Set<string>;
  onToggleSelect: (leadId: string) => void;
}) {
  return (
    <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
      {leads.map((lead) => (
        <article key={lead.public_id} className="relative rounded-2xl border border-border bg-card/95 p-4">
          <div className="absolute left-4 top-4">
            <Checkbox checked={selectedIds.has(lead.public_id)} onCheckedChange={() => onToggleSelect(lead.public_id)} />
          </div>
          <Link
            to={appPaths.leadDetail(lead.public_id)}
            className="absolute right-4 top-4 flex size-8 items-center justify-center rounded-full border border-border bg-muted/20 text-muted-foreground hover:text-foreground"
          >
            <ArrowUpRight className="size-3.5" />
          </Link>

          <div className="flex items-start gap-3 pt-8">
            <ScoreRing value={lead.latest_score ?? 0} size={60} stroke={5} />
            <div className="min-w-0">
              <p className="truncate text-base font-semibold">{lead.company_name}</p>
              <p className="text-sm text-muted-foreground">{lead.category ?? "Business"}</p>
              <div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
                <MapPin className="size-3.5" />
                <span>{lead.city ?? "Unknown city"}</span>
              </div>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <Badge tone={bandTone(lead.latest_band)}>{lead.latest_band ? titleCaseLabel(lead.latest_band) : "Unscored"}</Badge>
            <Badge tone={statusTone(lead.status)}>{titleCaseLabel(lead.status)}</Badge>
            <Badge tone="neutral">{formatScore(lead.latest_score)}</Badge>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
            <Signal label="Reviews" icon={<Star className="size-3.5 text-[oklch(var(--caution))]" />}>
              {lead.review_count}
            </Signal>
            <Signal label="Website" icon={<Globe className="size-3.5 text-muted-foreground" />}>
              {lead.website_domain ?? "Missing"}
            </Signal>
          </div>
        </article>
      ))}
    </div>
  );
}

function Signal({
  label,
  icon,
  children,
}: {
  label: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-muted/20 px-3 py-2">
      <div className="flex items-center gap-1 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="mt-1 truncate text-sm">{children}</div>
    </div>
  );
}
