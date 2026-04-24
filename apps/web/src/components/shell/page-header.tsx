import { cn } from "@/lib/utils";

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
  className,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  eyebrow?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-4 border-b border-border bg-background/60 px-3 py-4 sm:px-4 sm:py-5 lg:flex-row lg:items-end lg:justify-between lg:px-6 lg:py-6",
        className,
      )}
    >
      <div className="min-w-0 flex-1">
        {eyebrow && (
          <div className="mb-1.5 inline-flex items-center gap-1.5 rounded-full border border-[oklch(var(--signal)/0.3)] bg-[oklch(var(--signal)/0.08)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.12em] text-[oklch(var(--signal))]">
            {eyebrow}
          </div>
        )}
        <h1 className="text-pretty text-xl font-semibold tracking-tight sm:text-2xl lg:text-[26px]">{title}</h1>
        {description && (
          <p className="mt-1 text-pretty text-sm leading-relaxed text-muted-foreground lg:max-w-2xl">{description}</p>
        )}
      </div>
      {actions && <div className="flex w-full flex-wrap items-center gap-2 lg:w-auto lg:justify-end">{actions}</div>}
    </div>
  );
}
