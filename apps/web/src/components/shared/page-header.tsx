import type { PropsWithChildren, ReactNode } from "react";

type PageHeaderProps = PropsWithChildren<{
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}>;

export function PageHeader({ eyebrow, title, description, action }: PageHeaderProps) {
  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.24em] text-[color:var(--muted)]">
          {eyebrow}
        </p>
        <h1 className="mt-2 text-2xl font-extrabold">{title}</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-[color:var(--muted)]">{description}</p>
      </div>
      {action}
    </div>
  );
}

