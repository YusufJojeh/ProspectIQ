import type { PropsWithChildren } from "react";
import { cn } from "@/lib/utils";

type BadgeTone = "neutral" | "accent" | "warning";

const toneStyles: Record<BadgeTone, string> = {
  neutral: "bg-slate-100 text-slate-700",
  accent: "bg-[color:var(--accent-soft)] text-[color:var(--accent)]",
  warning: "bg-amber-100 text-amber-800",
};

export function Badge({
  children,
  tone = "neutral",
  className,
}: PropsWithChildren<{ tone?: BadgeTone; className?: string }>) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.12em]",
        toneStyles[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

