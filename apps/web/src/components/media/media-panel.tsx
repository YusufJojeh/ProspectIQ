import { cn } from "@/lib/utils";
import { HeroVideo, type HeroVideoProps } from "./hero-video";

interface MediaPanelProps extends HeroVideoProps {
  /** Headline text overlaid on the media */
  headline?: string;
  /** Subtext below the headline */
  subtext?: string;
  /** Badge/eyebrow text */
  eyebrow?: string;
  /** Bottom-aligned stats or trust signals */
  stats?: Array<{ label: string; value: string }>;
  /** Additional container classes */
  containerClassName?: string;
}

export function MediaPanel({
  headline,
  subtext,
  eyebrow,
  stats,
  containerClassName,
  ...videoProps
}: MediaPanelProps) {
  return (
    <div className={cn("relative h-full w-full", containerClassName)}>
      <HeroVideo
        {...videoProps}
        overlay="panel"
        className="absolute inset-0"
        aspect="h-full w-full"
      />

      {/* Ambient glow accents */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-0 top-0 h-[40%] w-[40%] bg-[radial-gradient(circle_at_top_left,rgba(20,184,166,0.2),transparent_60%)]" />
        <div className="absolute bottom-0 right-0 h-[35%] w-[35%] bg-[radial-gradient(circle_at_bottom_right,rgba(59,130,246,0.14),transparent_60%)]" />
      </div>

      {/* Mesh grid overlay */}
      <div className="pointer-events-none absolute inset-0 media-mesh-overlay opacity-[0.08]" />

      {/* Content overlay */}
      <div className="relative z-10 flex h-full flex-col justify-between p-8 lg:p-10">
        {/* Top content */}
        <div className="space-y-4">
          {eyebrow && (
            <span className="inline-flex items-center gap-2 rounded-full border border-border/30 bg-foreground/5 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.2em] text-[oklch(var(--signal))] backdrop-blur">
              <span className="h-1.5 w-1.5 rounded-full bg-[oklch(var(--signal))] shadow-[0_0_8px_oklch(var(--signal)/0.6)]" />
              {eyebrow}
            </span>
          )}
          {headline && (
            <h2 className="max-w-lg text-3xl font-bold tracking-tight text-foreground lg:text-4xl">
              {headline}
            </h2>
          )}
          {subtext && (
            <p className="max-w-md text-sm leading-7 text-muted-foreground">
              {subtext}
            </p>
          )}
        </div>

        {/* Bottom stats */}
        {stats && stats.length > 0 && (
          <div className="flex flex-wrap gap-3">
            {stats.map((stat) => (
              <div
                key={stat.label}
                className="rounded-2xl border border-border/20 bg-foreground/5 px-4 py-3 backdrop-blur"
              >
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                  {stat.label}
                </p>
                <p className="mt-1 text-lg font-semibold text-foreground">{stat.value}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
