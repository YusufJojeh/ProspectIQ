import { AlertCircle, Info, LoaderCircle } from "lucide-react";
import { cn } from "@/lib/utils";

type QueryStateNoticeProps = {
  title: string;
  description: string;
  tone?: "loading" | "error" | "info";
  className?: string;
};

const toneStyles = {
  loading: {
    icon: LoaderCircle,
    wrapper: "border-[color:var(--border)] bg-[color:var(--surface-soft)] text-[color:var(--text)]",
    iconClassName: "animate-spin text-[color:var(--accent)]",
  },
  error: {
    icon: AlertCircle,
    wrapper: "border-red-200 bg-red-50 text-red-950",
    iconClassName: "text-red-600",
  },
  info: {
    icon: Info,
    wrapper: "border-[color:var(--border)] bg-[color:var(--surface-soft)] text-[color:var(--text)]",
    iconClassName: "text-[color:var(--accent)]",
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
        "flex items-start gap-3 rounded-2xl border px-4 py-3",
        toneStyles[tone].wrapper,
        className,
      )}
      role={tone === "error" ? "alert" : "status"}
      aria-busy={tone === "loading"}
    >
      <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", toneStyles[tone].iconClassName)} />
      <div className="space-y-1">
        <p className="text-sm font-semibold">{title}</p>
        <p className="text-sm leading-6 opacity-85">{description}</p>
      </div>
    </div>
  );
}
