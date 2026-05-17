import type { ReactNode } from "react";
import { RotateCcw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function LeadsFiltersPanel({
  activeCount,
  children,
  onReset,
}: {
  activeCount: number;
  children: ReactNode;
  onReset: () => void;
}) {
  return (
    <aside className="w-full min-w-0 max-w-full overflow-hidden rounded-[1.5rem] border border-border bg-card/95 shadow-[0_20px_60px_-44px_rgba(15,23,42,0.85)] xl:sticky xl:top-20 xl:max-h-[calc(100vh-6.5rem)] xl:overflow-y-auto">
      <div className="flex min-w-0 items-center justify-between gap-2 border-b border-border px-4 py-4">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">Filter rail</h2>
          {activeCount > 0 ? <Badge tone="accent">{activeCount}</Badge> : null}
        </div>
        <Button variant="ghost" size="sm" className="gap-1.5" onClick={onReset}>
          <RotateCcw className="size-3.5" />
          Reset
        </Button>
      </div>
      <div className="space-y-4 p-4">{children}</div>
    </aside>
  );
}
