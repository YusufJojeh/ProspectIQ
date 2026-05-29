import { useTranslation } from "react-i18next";
import { Globe, Phone } from "lucide-react";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";

export function QuickFilterBar({
  scoreRange,
  onScoreRangeChange,
  hasWebsite,
  onHasWebsiteChange,
  hasPhone,
  onHasPhoneChange,
}: {
  scoreRange: [number, number];
  onScoreRangeChange: (range: [number, number]) => void;
  hasWebsite: "all" | "true" | "false";
  onHasWebsiteChange: (value: "all" | "true" | "false") => void;
  hasPhone: boolean;
  onHasPhoneChange: (value: boolean) => void;
}) {
  const { t } = useTranslation();

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-muted/10 px-3 py-2">
      <div className="flex min-w-[180px] flex-1 items-center gap-3">
        <span className="shrink-0 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          {t("leads.score")}
        </span>
        <Slider
          min={0}
          max={100}
          step={1}
          value={scoreRange}
          onValueChange={(v) => onScoreRangeChange(v as [number, number])}
          className="flex-1"
        />
        <span className="shrink-0 font-mono text-[11px] tabular-nums text-muted-foreground">
          {scoreRange[0]}–{scoreRange[1]}
        </span>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant={hasWebsite === "true" ? "default" : "outline"}
          size="sm"
          className={`h-7 gap-1.5 text-xs ${hasWebsite === "true" ? "" : "bg-transparent"}`}
          onClick={() => onHasWebsiteChange(hasWebsite === "true" ? "all" : "true")}
        >
          <Globe className="size-3" />
          {t("leads.hasWebsite")}
        </Button>

        <Button
          variant={hasPhone ? "default" : "outline"}
          size="sm"
          className={`h-7 gap-1.5 text-xs ${hasPhone ? "" : "bg-transparent"}`}
          onClick={() => onHasPhoneChange(!hasPhone)}
        >
          <Phone className="size-3" />
          {t("leads.hasPhone")}
        </Button>
      </div>
    </div>
  );
}
