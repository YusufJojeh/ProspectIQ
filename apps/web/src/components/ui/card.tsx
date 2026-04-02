import type { HTMLAttributes, PropsWithChildren } from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-xl border border-[color:var(--border)] bg-white/85 shadow-[0_18px_40px_-32px_rgba(15,23,42,0.3)]",
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("border-b border-[color:var(--border)] p-5", className)} {...props} />;
}

export function CardTitle({ className, children }: PropsWithChildren<{ className?: string }>) {
  return <h3 className={cn("text-lg font-bold", className)}>{children}</h3>;
}

export function CardDescription({ className, children }: PropsWithChildren<{ className?: string }>) {
  return <p className={cn("mt-1 text-sm text-[color:var(--muted)]", className)}>{children}</p>;
}

export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5", className)} {...props} />;
}

