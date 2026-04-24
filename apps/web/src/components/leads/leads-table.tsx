import type { KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { appPaths } from "@/app/paths";
import { ScoreRing } from "@/components/brand/score-ring";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { bandTone, formatScore, statusTone, titleCaseLabel } from "@/lib/presenters";
import type { LeadResponse } from "@/types/api";

export function LeadsTable({
  leads,
  selectedLeadId,
  selectedIds,
  onSelectLead,
  onToggleSelect,
}: {
  leads: LeadResponse[];
  selectedLeadId: string | null;
  selectedIds: Set<string>;
  onSelectLead: (leadId: string) => void;
  onToggleSelect: (leadId: string) => void;
}) {
  return (
    <Table className="min-w-[860px]">
      <TableHeader className="bg-muted/30">
        <TableRow className="hover:bg-transparent">
          <TableHead className="w-12" />
          <TableHead>Lead</TableHead>
          <TableHead>Coverage</TableHead>
          <TableHead>Score</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Website</TableHead>
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
          />
        ))}
      </TableBody>
    </Table>
  );
}

function LeadTableRow({
  lead,
  isSelected,
  isChecked,
  onSelectLead,
  onToggleSelect,
}: {
  lead: LeadResponse;
  isSelected: boolean;
  isChecked: boolean;
  onSelectLead: (leadId: string) => void;
  onToggleSelect: (leadId: string) => void;
}) {
  const handleKeyDown = (event: KeyboardEvent<HTMLTableRowElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelectLead(lead.public_id);
    }
  };

  return (
    <TableRow
      data-state={isSelected ? "selected" : undefined}
      className={isSelected ? "bg-[oklch(var(--signal)/0.07)]" : "bg-transparent"}
      role="button"
      tabIndex={0}
      onClick={() => onSelectLead(lead.public_id)}
      onKeyDown={handleKeyDown}
    >
      <TableCell onClick={(event) => event.stopPropagation()}>
        <Checkbox checked={isChecked} onCheckedChange={() => onToggleSelect(lead.public_id)} />
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-3">
          <ScoreRing value={lead.latest_score ?? 0} size={44} stroke={4} showBand={false} />
          <div className="min-w-0">
            <Link className="font-semibold hover:text-[oklch(var(--signal))]" to={appPaths.leadDetail(lead.public_id)}>
              {lead.company_name}
            </Link>
            <p className="text-sm text-muted-foreground">
              {lead.category ?? "Business"} · {lead.city ?? "Unknown"}
            </p>
          </div>
        </div>
      </TableCell>
      <TableCell>
        <div className="flex flex-wrap gap-2">
          <Badge tone={bandTone(lead.latest_band)}>{lead.latest_band ? titleCaseLabel(lead.latest_band) : "Unscored"}</Badge>
          <Badge tone={lead.latest_qualified ? "success" : "neutral"}>
            {lead.latest_qualified ? "Qualified" : "Needs review"}
          </Badge>
        </div>
      </TableCell>
      <TableCell className="font-mono tabular-nums">{formatScore(lead.latest_score)}</TableCell>
      <TableCell>
        <Badge tone={statusTone(lead.status)}>{titleCaseLabel(lead.status)}</Badge>
      </TableCell>
      <TableCell className="text-sm text-muted-foreground">{lead.website_domain ?? "Missing"}</TableCell>
    </TableRow>
  );
}
