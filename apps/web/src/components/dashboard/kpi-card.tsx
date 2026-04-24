import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";

export function KpiCard({
  label,
  value,
  helper,
  delta,
  tone = "signal",
  icon: Icon,
}: {
  label: string;
  value: string;
  helper: string;
  delta?: string;
  tone?: "signal" | "evidence" | "caution" | "risk";
  icon?: React.ComponentType<{ className?: string }>;
}) {
  const toneClass =
    tone === "evidence"
      ? "text-[oklch(var(--evidence))] border-[oklch(var(--evidence)/0.25)] bg-[oklch(var(--evidence)/0.08)]"
      : tone === "caution"
        ? "text-[oklch(var(--caution))] border-[oklch(var(--caution)/0.25)] bg-[oklch(var(--caution)/0.08)]"
        : tone === "risk"
          ? "text-[oklch(var(--risk))] border-[oklch(var(--risk)/0.25)] bg-[oklch(var(--risk)/0.08)]"
          : "text-[oklch(var(--signal))] border-[oklch(var(--signal)/0.25)] bg-[oklch(var(--signal)/0.08)]";

  return (
    <div className="group relative overflow-hidden rounded-2xl border border-border bg-card/95 p-5 shadow-[0_20px_60px_-44px_rgba(15,23,42,0.85)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
          <p className="mt-3 font-mono text-3xl font-semibold tracking-tight tabular-nums">{value}</p>
        </div>
        {Icon ? (
          <div className={cn("rounded-xl border p-3", toneClass)}>
            <Icon className="size-4" />
          </div>
        ) : null}
      </div>

      <div className="mt-4 flex items-center justify-between gap-3">
        <p className="max-w-[18rem] text-sm leading-6 text-muted-foreground">{helper}</p>
        {delta ? (
          <div className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[11px] font-medium", toneClass)}>
            {tone === "risk" ? <ArrowDownRight className="size-3" /> : <ArrowUpRight className="size-3" />}
            {delta}
          </div>
        ) : null}
      </div>
    </div>
  );
}
