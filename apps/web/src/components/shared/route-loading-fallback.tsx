import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Skeleton } from "@/components/ui/skeleton";

type RouteLoadingFallbackProps = {
  title?: string;
  description?: string;
  compact?: boolean;
};

export function RouteLoadingFallback({
  title = "Loading workspace view",
  description = "Preparing the route bundle and rendering the next screen.",
  compact = false,
}: RouteLoadingFallbackProps) {
  if (compact) {
    return (
      <div className="space-y-4">
        <QueryStateNotice tone="loading" title={title} description={description} />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Skeleton className="h-28 rounded-2xl" />
          <Skeleton className="h-28 rounded-2xl" />
          <Skeleton className="h-28 rounded-2xl" />
          <Skeleton className="h-28 rounded-2xl" />
        </div>
        <Skeleton className="h-[320px] rounded-2xl" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <QueryStateNotice tone="loading" title={title} description={description} />
      <Skeleton className="h-[420px] rounded-2xl" />
    </div>
  );
}
