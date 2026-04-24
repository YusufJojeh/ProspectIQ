import { cn } from "@/lib/utils";
import { ShieldCheck, TriangleAlert, Zap, CircleDot } from "lucide-react";

export type ScoreBand = "A" | "B" | "C" | "D" | "E";

export function bandColor(band: ScoreBand): string {
  return (
    band === "A"
      ? "text-[oklch(var(--score-a))] border-[oklch(var(--score-a)/0.35)] bg-[oklch(var(--score-a)/0.1)]"
      : band === "B"
        ? "text-[oklch(var(--score-b))] border-[oklch(var(--score-b)/0.35)] bg-[oklch(var(--score-b)/0.1)]"
        : band === "C"
          ? "text-[oklch(var(--score-c))] border-[oklch(var(--score-c)/0.35)] bg-[oklch(var(--score-c)/0.1)]"
          : band === "D"
            ? "text-[oklch(var(--score-d))] border-[oklch(var(--score-d)/0.35)] bg-[oklch(var(--score-d)/0.1)]"
            : "text-[oklch(var(--score-e))] border-[oklch(var(--score-e)/0.35)] bg-[oklch(var(--score-e)/0.1)]"
  );
}

export function bandFromScore(score: number): ScoreBand {
  if (score >= 85) return "A";
  if (score >= 70) return "B";
  if (score >= 55) return "C";
  if (score >= 40) return "D";
  return "E";
}

export function BandBadge({ band, className }: { band: ScoreBand; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider",
        bandColor(band),
        className,
      )}
    >
      <CircleDot className="size-2.5" />
      Band {band}
    </span>
  );
}

export function ConfidenceBadge({ value, className }: { value: number; className?: string }) {
  const pct = Math.round(value * 100);
  const tone =
    pct >= 85
      ? "text-[oklch(var(--evidence))] border-[oklch(var(--evidence)/0.35)] bg-[oklch(var(--evidence)/0.1)]"
      : pct >= 70
        ? "text-[oklch(var(--signal))] border-[oklch(var(--signal)/0.35)] bg-[oklch(var(--signal)/0.1)]"
        : pct >= 55
          ? "text-[oklch(var(--caution))] border-[oklch(var(--caution)/0.35)] bg-[oklch(var(--caution)/0.1)]"
          : "text-[oklch(var(--risk))] border-[oklch(var(--risk)/0.35)] bg-[oklch(var(--risk)/0.1)]";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 font-mono text-[10px] font-medium tabular-nums",
        tone,
        className,
      )}
    >
      <ShieldCheck className="size-3" />
      {pct}% confidence
    </span>
  );
}

export function EvidenceChip({
  label,
  tone = "default",
  className,
}: {
  label: string;
  tone?: "default" | "evidence" | "signal" | "caution" | "risk";
  className?: string;
}) {
  const toneCls = {
    default: "text-muted-foreground border-border bg-muted/40",
    evidence: "text-[oklch(var(--evidence))] border-[oklch(var(--evidence)/0.3)] bg-[oklch(var(--evidence)/0.08)]",
    signal: "text-[oklch(var(--signal))] border-[oklch(var(--signal)/0.3)] bg-[oklch(var(--signal)/0.08)]",
    caution: "text-[oklch(var(--caution))] border-[oklch(var(--caution)/0.3)] bg-[oklch(var(--caution)/0.08)]",
    risk: "text-[oklch(var(--risk))] border-[oklch(var(--risk)/0.3)] bg-[oklch(var(--risk)/0.08)]",
  }[tone];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium",
        toneCls,
        className,
      )}
    >
      {label}
    </span>
  );
}

export function StatusDot({ status, className }: { status: string; className?: string }) {
  const map: Record<string, string> = {
    running: "bg-[oklch(var(--signal))] shadow-[0_0_0_3px_oklch(var(--signal)/0.2)]",
    queued: "bg-muted-foreground",
    completed: "bg-[oklch(var(--evidence))]",
    partial: "bg-[oklch(var(--caution))]",
    partially_completed: "bg-[oklch(var(--caution))]",
    failed: "bg-[oklch(var(--risk))]",
    new: "bg-[oklch(var(--signal))]",
    reviewed: "bg-[oklch(var(--signal))]",
    qualified: "bg-[oklch(var(--evidence))]",
    contacted: "bg-[oklch(var(--caution))]",
    interested: "bg-[oklch(var(--caution))]",
    replied: "bg-[oklch(var(--signal))]",
    won: "bg-[oklch(var(--evidence))]",
    lost: "bg-[oklch(var(--risk))]",
    archived: "bg-muted-foreground",
    active: "bg-[oklch(var(--evidence))]",
    invited: "bg-[oklch(var(--caution))]",
    suspended: "bg-[oklch(var(--risk))]",
    ready: "bg-[oklch(var(--evidence))]",
    expired: "bg-muted-foreground",
    high: "bg-[oklch(var(--score-a))]",
    medium: "bg-[oklch(var(--score-c))]",
    low: "bg-[oklch(var(--score-e))]",
    not_qualified: "bg-muted-foreground",
  };
  return <span className={cn("inline-block size-2 rounded-full", map[status] ?? "bg-muted-foreground", className)} />;
}

export function AiPill({ className, children }: { className?: string; children?: React.ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-[oklch(var(--signal)/0.35)] bg-[oklch(var(--signal)/0.08)] px-2 py-0.5 text-[11px] font-medium text-[oklch(var(--signal))]",
        className,
      )}
    >
      <Zap className="size-3" />
      {children ?? "Assistive AI"}
    </span>
  );
}

export function AttentionPill({ className, children }: { className?: string; children?: React.ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-[oklch(var(--caution)/0.35)] bg-[oklch(var(--caution)/0.08)] px-2 py-0.5 text-[11px] font-medium text-[oklch(var(--caution))]",
        className,
      )}
    >
      <TriangleAlert className="size-3" />
      {children ?? "Attention"}
    </span>
  );
}
