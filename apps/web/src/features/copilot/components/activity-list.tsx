import { useTranslation } from "react-i18next";
import { CheckCircle2, CircleAlert, CircleDot, Info, LoaderCircle } from "lucide-react";

import { cn } from "@/lib/utils";

import type { ActivityItem, ActivityTone } from "../agent-state";

const ICONS: Record<ActivityTone, typeof Info> = {
  progress: LoaderCircle,
  success: CheckCircle2,
  warning: CircleAlert,
  danger: CircleAlert,
  info: CircleDot,
};

const TONE_CLASS: Record<ActivityTone, string> = {
  progress: "text-[oklch(var(--signal))]",
  success: "text-[oklch(var(--evidence))]",
  warning: "text-[oklch(var(--caution))]",
  danger: "text-destructive",
  info: "text-muted-foreground",
};

interface ActivityListProps {
  items: ActivityItem[];
  /** The run is still working; the newest step animates. */
  live: boolean;
}

/**
 * Friendly, sanitized progress. Only the category of work is shown: no tool
 * arguments, raw payloads or model reasoning ever reach this list.
 */
export function ActivityList({ items, live }: ActivityListProps) {
  const { t } = useTranslation();
  if (items.length === 0) return null;
  const lastIndex = items.length - 1;

  return (
    <ol
      aria-label={t("copilot.activity.title")}
      aria-live="polite"
      className="space-y-1.5 text-sm"
    >
      {items.map((item, index) => {
        const Icon = ICONS[item.tone];
        const spinning = live && index === lastIndex && item.tone === "progress";
        return (
          <li key={item.eventId} className="flex items-start gap-2">
            <Icon
              aria-hidden
              className={cn("mt-0.5 size-3.5 shrink-0", TONE_CLASS[item.tone], spinning && "animate-spin")}
            />
            <span className={index === lastIndex ? "text-foreground" : "text-muted-foreground"}>
              {t(item.labelKey, item.params)}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
