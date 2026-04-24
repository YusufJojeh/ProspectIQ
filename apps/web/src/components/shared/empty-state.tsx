import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type EmptyStateProps = {
  title: string;
  description: string;
  action?: ReactNode;
  className?: string;
};

export function EmptyState({ title, description, action, className }: EmptyStateProps) {
  return (
    <Card className={cn("border-dashed bg-[color:var(--surface-contrast)]", className)}>
      <CardContent className="space-y-4 py-10 text-center">
        <div className="flex justify-center">
          <Badge tone="neutral">No data</Badge>
        </div>
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="mx-auto max-w-xl text-sm leading-6 text-[color:var(--muted)]">{description}</p>
        {action}
      </CardContent>
    </Card>
  );
}
