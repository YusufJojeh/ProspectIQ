import { Suspense, lazy, type ComponentProps } from "react";
import { Skeleton } from "@/components/ui/skeleton";

const LeadMap = lazy(async () => {
  const module = await import("./lead-map");
  return { default: module.LeadMap };
});

type LeadMapProps = ComponentProps<typeof LeadMap>;

export function LazyLeadMap(props: LeadMapProps) {
  return (
    <Suspense fallback={<Skeleton className="h-full min-h-[220px] rounded-[inherit]" />}>
      <LeadMap {...props} />
    </Suspense>
  );
}
