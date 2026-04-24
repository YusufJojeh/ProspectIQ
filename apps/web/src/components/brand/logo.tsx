import { cn } from "@/lib/utils";

export function LeadScopeMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={cn("size-7", className)}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="ls-grad" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="oklch(0.88 0.14 195)" />
          <stop offset="1" stopColor="oklch(0.62 0.12 210)" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="30" height="30" rx="8" fill="oklch(0.18 0.01 240)" stroke="oklch(0.28 0.01 240)" />
      <circle cx="16" cy="16" r="8.5" stroke="url(#ls-grad)" strokeWidth="1.5" />
      <circle cx="16" cy="16" r="3.2" fill="url(#ls-grad)" />
      <path d="M22 22L26 26" stroke="url(#ls-grad)" strokeWidth="2" strokeLinecap="round" />
      <path d="M16 4V7.5" stroke="oklch(0.82 0.14 195 / 0.6)" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M16 24.5V28" stroke="oklch(0.82 0.14 195 / 0.6)" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M4 16H7.5" stroke="oklch(0.82 0.14 195 / 0.6)" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M24.5 16H28" stroke="oklch(0.82 0.14 195 / 0.6)" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

export function LeadScopeWordmark({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <LeadScopeMark />
      <div className="flex flex-col leading-none">
        <span className="text-[15px] font-semibold tracking-tight text-foreground">LeadScope</span>
        <span className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
          Intelligence
        </span>
      </div>
    </div>
  );
}
