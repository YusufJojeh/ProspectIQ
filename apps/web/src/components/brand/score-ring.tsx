import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { bandFromScore, type ScoreBand } from "@/components/brand/badges";

export function ScoreRing({
  value,
  size = 72,
  stroke = 6,
  className,
  showBand = true,
}: {
  value: number;
  size?: number;
  stroke?: number;
  className?: string;
  showBand?: boolean;
}) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const band: ScoreBand = bandFromScore(value);
  const color =
    band === "A"
      ? "oklch(var(--score-a))"
      : band === "B"
        ? "oklch(var(--score-b))"
        : band === "C"
          ? "oklch(var(--score-c))"
          : band === "D"
            ? "oklch(var(--score-d))"
            : "oklch(var(--score-e))";

  const offset = circumference - (value / 100) * circumference;

  return (
    <div
      className={cn("relative inline-flex items-center justify-center", className)}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} stroke="oklch(var(--border))" strokeWidth={stroke} fill="none" />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          fill="none"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          style={{ filter: `drop-shadow(0 0 6px ${color})` }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-base font-semibold tabular-nums tracking-tight text-foreground">{value}</span>
        {showBand && (
          <span className="-mt-0.5 text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
            Band {band}
          </span>
        )}
      </div>
    </div>
  );
}
