import { useQuery } from "@tanstack/react-query";
import { listSearchJobs } from "@/features/searches/api";

const ACTIVE_STATUSES = new Set(["queued", "running"]);

/**
 * Shared TanStack Query subscription for workspace search jobs (single cache key everywhere).
 */
export function useSearchJobsQuery() {
  return useQuery({
    queryKey: ["search-jobs"],
    queryFn: listSearchJobs,
    staleTime: 10_000,
    refetchInterval: (query) => {
      const items = query.state.data?.items;
      if (!items?.length) {
        return false;
      }
      return items.some((job) => ACTIVE_STATUSES.has(job.status)) ? 4_000 : false;
    },
  });
}
