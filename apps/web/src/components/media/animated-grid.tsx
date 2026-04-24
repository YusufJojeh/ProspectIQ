import { cn } from "@/lib/utils";

interface AnimatedGridProps {
  className?: string;
}

/**
 * A subtle animated dot-grid background that reinforces the
 * "digital signals / data network" visual identity.
 * Pure CSS — no JS animation cost.
 */
export function AnimatedGrid({ className }: AnimatedGridProps) {
  return (
    <div className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}>
      {/* Dot grid */}
      <div className="absolute inset-0 animated-dot-grid opacity-[0.35]" />

      {/* Horizontal scan line */}
      <div className="absolute inset-x-0 h-px animated-scan-line" />

      {/* Floating orbs */}
      <div className="absolute left-[15%] top-[20%] h-64 w-64 rounded-full bg-teal-500/[0.07] blur-[80px] animated-orb" />
      <div className="absolute right-[10%] bottom-[15%] h-48 w-48 rounded-full bg-blue-500/[0.06] blur-[60px] animated-orb-reverse" />
      <div className="absolute left-[60%] top-[60%] h-32 w-32 rounded-full bg-teal-400/[0.05] blur-[50px] animated-orb-slow" />
    </div>
  );
}
