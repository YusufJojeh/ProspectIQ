import type { KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Columns3 } from "lucide-react";
import { appPaths } from "@/app/paths";
import { LeadScoreSpinner } from "@/components/brand/lead-score-spinner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { leadStatusLabel, scoreBandLabel } from "@/lib/i18n-labels";
import { bandTone, formatScore, statusTone } from "@/lib/presenters";
import type { BadgeTone } from "@/components/ui/badge";
import type { ColumnVisibility } from "@/hooks/use-column-visibility";
import type { LeadResponse } from "@/types/api";

function outreachStatusTone(status: string): BadgeTone {
  if (status === "sent") return "success";
  if (status === "replied") return "signal";
  return "neutral";
}

function signalStrengthTone(strength: number | null): BadgeTone {
  if (strength === null) return "neutral";
  const pct = strength <= 1 ? strength * 100 : strength;
  if (pct >= 70) return "success";
  if (pct >= 40) return "warning";
  return "neutral";
}

export function LeadsTable({
  leads,
  selectedLeadId,
  selectedIds,
  onSelectLead,
  onToggleSelect,
  visibility,
  onToggleColumn,
}: {
  leads: LeadResponse[];
  selectedLeadId: string | null;
  selectedIds: Set<string>;
  onSelectLead: (leadId: string) => void;
  onToggleSelect: (leadId: string) => void;
  visibility?: ColumnVisibility;
  onToggleColumn?: (key: keyof ColumnVisibility, value: boolean) => void;
}) {
  const { t } = useTranslation();
  const vis: ColumnVisibility = visibility ?? {
    score: true,
    coverage: true,
    phone: false,
    website: true,
    industry: false,
    signal: true,
  };
  return (
    <div className="space-y-2">
      {onToggleColumn && (
        <div className="flex justify-end">
          <ColumnToggle visibility={vis} onToggle={onToggleColumn} />
        </div>
      )}
      <Table className="min-w-[860px]">
        <TableHeader className="bg-muted/30">
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-12" />
            <TableHead>{t("leads.lead")}</TableHead>
            {vis.coverage && <TableHead>{t("leads.coverage")}</TableHead>}
            {vis.score && <TableHead>{t("leads.score")}</TableHead>}
            {vis.industry && <TableHead>{t("leads.industry")}</TableHead>}
            {vis.signal && <TableHead>{t("leads.topSignal")}</TableHead>}
            <TableHead>{t("leads.status")}</TableHead>
            {vis.phone && <TableHead>{t("leads.phone")}</TableHead>}
            <TableHead>{t("leads.outreach")}</TableHead>
            {vis.website && <TableHead>{t("leads.website")}</TableHead>}
          </TableRow>
        </TableHeader>
        <TableBody>
          {leads.map((lead) => (
            <LeadTableRow
              key={lead.public_id}
              lead={lead}
              isSelected={lead.public_id === selectedLeadId}
              isChecked={selectedIds.has(lead.public_id)}
              onSelectLead={onSelectLead}
              onToggleSelect={onToggleSelect}
              visibility={vis}
            />
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function ColumnToggle({
  visibility,
  onToggle,
}: {
  visibility: ColumnVisibility;
  onToggle: (key: keyof ColumnVisibility, value: boolean) => void;
}) {
  const { t } = useTranslation();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="h-7 gap-1.5 bg-transparent text-xs"
        >
          <Columns3 className="size-3.5" />
          {t("leads.columns")}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-40">
        <DropdownMenuLabel className="text-xs">
          {t("leads.columns")}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {(
          [
            { key: "coverage", label: t("leads.coverage") },
            { key: "score", label: t("leads.score") },
            { key: "industry", label: t("leads.industry") },
            { key: "signal", label: t("leads.topSignal") },
            { key: "phone", label: t("leads.phone") },
            { key: "website", label: t("leads.website") },
          ] as const
        ).map(({ key, label }) => (
          <DropdownMenuCheckboxItem
            key={key}
            checked={visibility[key]}
            onCheckedChange={(checked) => onToggle(key, Boolean(checked))}
          >
            {label}
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function LeadTableRow({
  lead,
  isSelected,
  isChecked,
  onSelectLead,
  onToggleSelect,
  visibility,
}: {
  lead: LeadResponse;
  isSelected: boolean;
  isChecked: boolean;
  onSelectLead: (leadId: string) => void;
  onToggleSelect: (leadId: string) => void;
  visibility: ColumnVisibility;
}) {
  const { t } = useTranslation();
  const priorityScore = lead.latest_final_priority_score ?? lead.latest_score;
  const handleKeyDown = (event: KeyboardEvent<HTMLTableRowElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelectLead(lead.public_id);
    }
  };

  return (
    <TableRow
      data-state={isSelected ? "selected" : undefined}
      className={
        isSelected ? "bg-[oklch(var(--signal)/0.07)]" : "bg-transparent"
      }
      role="button"
      tabIndex={0}
      onClick={() => onSelectLead(lead.public_id)}
      onKeyDown={handleKeyDown}
    >
      <TableCell onClick={(event) => event.stopPropagation()}>
        <Checkbox
          checked={isChecked}
          onCheckedChange={() => onToggleSelect(lead.public_id)}
        />
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-3">
          <LeadScoreSpinner
            value={priorityScore ?? 0}
            size={44}
            stroke={4}
            label={t("leadScoreSpinner.companyScore", {
              company: lead.company_name,
              score: Math.round(priorityScore ?? 0),
            })}
          />
          <div className="min-w-0">
            <Link
              className="font-semibold hover:text-[oklch(var(--signal))]"
              to={appPaths.leadDetail(lead.public_id)}
            >
              {lead.company_name}
            </Link>
            <p className="text-sm text-muted-foreground">
              {lead.category ?? t("leads.business")} ·{" "}
              {lead.city ?? t("common.unknown")}
            </p>
          </div>
        </div>
      </TableCell>
      {visibility.coverage && (
        <TableCell>
          <div className="flex flex-wrap gap-2">
            <Badge tone={bandTone(lead.latest_band)}>
              {scoreBandLabel(t, lead.latest_band)}
            </Badge>
            <Badge tone={lead.latest_qualified ? "success" : "neutral"}>
              {lead.latest_qualified
                ? t("leads.qualified")
                : t("leads.needsReview")}
            </Badge>
            {lead.latest_fit_score != null ? (
              <Badge tone="info">
                {t("leads.fitScore")}: {formatScore(lead.latest_fit_score)}
              </Badge>
            ) : null}
          </div>
        </TableCell>
      )}
      {visibility.score && (
        <TableCell className="font-mono tabular-nums">
          <div className="space-y-1">
            <p>{formatScore(priorityScore)}</p>
            {lead.latest_final_priority_score != null ? (
              <p className="text-xs text-muted-foreground">
                {t("leads.finalPriorityScore")}
              </p>
            ) : null}
          </div>
        </TableCell>
      )}
      {visibility.industry && (
        <TableCell className="text-sm text-muted-foreground">
          {lead.industry ?? "—"}
        </TableCell>
      )}
      {visibility.signal && (
        <TableCell>
          {lead.top_signal_type ? (
            <div className="flex items-center gap-2">
              <Badge
                tone={signalStrengthTone(lead.top_signal_strength)}
                className="max-w-[12rem]"
                title={lead.top_signal_evidence ?? undefined}
              >
                <span className="truncate">
                  {t(`leadDetail.signals.types.${lead.top_signal_type}`, {
                    defaultValue: lead.top_signal_type.replace(/_/g, " "),
                  })}
                </span>
              </Badge>
              {lead.signals_count > 1 ? (
                <span className="text-xs text-muted-foreground">
                  +{lead.signals_count - 1}
                </span>
              ) : null}
            </div>
          ) : (
            <span className="text-sm text-muted-foreground">—</span>
          )}
        </TableCell>
      )}
      <TableCell>
        <Badge tone={statusTone(lead.status)}>
          {leadStatusLabel(t, lead.status)}
        </Badge>
      </TableCell>
      {visibility.phone && (
        <TableCell className="text-sm text-muted-foreground">
          {lead.phone ?? "—"}
        </TableCell>
      )}
      <TableCell>
        {lead.latest_outreach_status ? (
          <Badge tone={outreachStatusTone(lead.latest_outreach_status)}>
            {t(`leads.outreachStatus.${lead.latest_outreach_status}`)}
          </Badge>
        ) : (
          <span className="text-sm text-muted-foreground">—</span>
        )}
      </TableCell>
      {visibility.website && (
        <TableCell className="text-sm text-muted-foreground">
          {lead.website_domain ?? t("leads.missing")}
        </TableCell>
      )}
    </TableRow>
  );
}
