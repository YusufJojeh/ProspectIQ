import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type EmptyStateProps = {
  title: string;
  description: string;
  action?: ReactNode;
  className?: string;
};

export function EmptyState({ title, description, action, className }: EmptyStateProps) {
  return (
    <Card className={cn("border-dashed bg-white/70", className)}>
      <CardContent className="space-y-3 py-10 text-center">
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="mx-auto max-w-xl text-sm leading-6 text-[color:var(--muted)]">{description}</p>
        {action}
      </CardContent>
    </Card>
  );
}
