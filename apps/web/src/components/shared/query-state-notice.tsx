import { AlertCircle, CheckCircle2, Info, LoaderCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type QueryStateNoticeProps = {
  title: string;
  description: string;
  tone?: "loading" | "error" | "info" | "success";
  className?: string;
};

const toneStyles = {
  loading: {
    icon: LoaderCircle,
    wrapper: "border-border bg-card/95 text-foreground",
    iconClassName: "animate-spin text-[oklch(var(--signal))]",
  },
  error: {
    icon: AlertCircle,
    wrapper: "border-destructive/30 bg-destructive/10 text-foreground",
    iconClassName: "text-destructive",
  },
  info: {
    icon: Info,
    wrapper: "border-border bg-card/95 text-foreground",
    iconClassName: "text-[oklch(var(--signal))]",
  },
  success: {
    icon: CheckCircle2,
    wrapper:
      "border-[oklch(var(--evidence)/0.3)] bg-[oklch(var(--evidence)/0.1)] text-foreground",
    iconClassName: "text-[oklch(var(--evidence))]",
  },
} as const;

export function QueryStateNotice({
  title,
  description,
  tone = "info",
  className,
}: QueryStateNoticeProps) {
  const Icon = toneStyles[tone].icon;

  return (
    <div
      className={cn(
        "flex items-start gap-4 rounded-2xl border px-4 py-4 shadow-[0_18px_38px_-28px_rgba(15,23,42,0.45)] backdrop-blur",
        toneStyles[tone].wrapper,
        className,
      )}
      role={tone === "error" ? "alert" : "status"}
      aria-busy={tone === "loading"}
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-card/80 shadow-sm">
        <Icon className={cn("h-4 w-4 shrink-0", toneStyles[tone].iconClassName)} />
      </div>
      <div className="space-y-2">
        <Badge tone={tone === "error" ? "danger" : tone === "success" ? "success" : "neutral"} className="w-fit">
          {tone}
        </Badge>
        <p className="text-sm font-semibold">{title}</p>
        <p className="text-sm leading-6 text-[color:var(--muted)]">{description}</p>
      </div>
    </div>
  );
}
