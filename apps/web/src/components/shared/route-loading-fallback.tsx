import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Skeleton } from "@/components/ui/skeleton";
import { useTranslation } from "react-i18next";

type RouteLoadingFallbackProps = {
  title?: string;
  description?: string;
  compact?: boolean;
};

export function RouteLoadingFallback({
  title,
  description,
  compact = false,
}: RouteLoadingFallbackProps) {
  const { t } = useTranslation();
  const resolvedTitle = title ?? t("routeLoading.defaultTitle");
  const resolvedDescription =
    description ?? t("routeLoading.defaultDescription");

  if (compact) {
    return (
      <div className="space-y-4">
        <QueryStateNotice
          tone="loading"
          title={resolvedTitle}
          description={resolvedDescription}
        />
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
      <QueryStateNotice
        tone="loading"
        title={resolvedTitle}
        description={resolvedDescription}
      />
      <Skeleton className="h-[420px] rounded-2xl" />
    </div>
  );
}
