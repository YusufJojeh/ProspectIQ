import { cn } from "@/lib/utils";

export type LeadScoreSpinnerVariant = "hot" | "warm" | "research" | "low" | "danger";

const variantStroke: Record<LeadScoreSpinnerVariant, string> = {
  hot: "oklch(var(--score-a))",
  warm: "oklch(var(--score-b))",
  research: "oklch(var(--score-c))",
  low: "oklch(var(--score-d))",
  danger: "oklch(var(--score-e))",
};

export function leadScoreVariant(value: number | null | undefined): LeadScoreSpinnerVariant {
  const score = clampScore(value ?? 0);
  if (score >= 85) return "hot";
  if (score >= 70) return "warm";
  if (score >= 55) return "research";
  if (score >= 40) return "low";
  return "danger";
}

export function clampScore(value: number): number {
  return Math.min(100, Math.max(0, Math.round(value)));
}

export function LeadScoreSpinner({
  value,
  variant,
  size = 52,
  stroke = 5,
  className,
  label,
}: {
  value: number | null | undefined;
  variant?: LeadScoreSpinnerVariant;
  size?: number;
  stroke?: number;
  className?: string;
  label?: string;
}) {
  const score = clampScore(value ?? 0);
  const resolvedVariant = variant ?? leadScoreVariant(score);
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const strokeColor = variantStroke[resolvedVariant];
  const ariaLabel = label ?? `Lead score ${score} percent`;

  return (
    <div
      className={cn("relative inline-flex shrink-0 items-center justify-center", className)}
      style={{ width: size, height: size }}
      role="img"
      aria-label={ariaLabel}
    >
      <svg width={size} height={size} className="-rotate-90" aria-hidden="true">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="oklch(var(--border))"
          strokeWidth={stroke}
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={strokeColor}
          strokeWidth={stroke}
          strokeLinecap="round"
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <span className="absolute font-mono text-[12px] font-semibold tabular-nums">
        {score}%
      </span>
    </div>
  );
}
