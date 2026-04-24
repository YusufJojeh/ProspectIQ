import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { SearchJobResponse } from "@/types/api";

const INTERVAL_MS = 5_000;

/**
 * While any search job is queued or running, periodically invalidate lead queries so lists/maps
 * pick up new rows without a full page reload (discovery runs in API background tasks).
 */
export function useInvalidateLeadsWhileDiscoveryActive(jobs: SearchJobResponse[] | undefined) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!jobs?.length) {
      return;
    }
    const hasActive = jobs.some((job) => job.status === "queued" || job.status === "running");
    if (!hasActive) {
      return;
    }
    const handle = window.setInterval(() => {
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
    }, INTERVAL_MS);
    return () => window.clearInterval(handle);
  }, [jobs, queryClient]);
}
