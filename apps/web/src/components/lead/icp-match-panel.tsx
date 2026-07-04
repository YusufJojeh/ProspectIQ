import { useTranslation } from "react-i18next";
import { EmptyState } from "@/components/shared/empty-state";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatDate, formatScore } from "@/lib/presenters";
import type {
  IcpProfileResponse,
  LeadIcpMatchResponse,
  LeadResponse,
  LeadScoreBreakdownResponse,
} from "@/types/api";

export function LeadIcpMatchPanel({
  lead,
  breakdown,
  profiles,
  profilesLoading,
  profilesError,
  selectedProfileId,
  lastMatch,
  recomputing,
  onProfileChange,
  onRecompute,
}: {
  lead: LeadResponse;
  breakdown: LeadScoreBreakdownResponse | null;
  profiles: IcpProfileResponse[];
  profilesLoading: boolean;
  profilesError: Error | null;
  selectedProfileId: string;
  lastMatch: LeadIcpMatchResponse | null;
  recomputing: boolean;
  onProfileChange: (profileId: string) => void;
  onRecompute: () => void;
}) {
  const { t } = useTranslation();
  const storedFitScore = breakdown?.fit_score ?? lead.latest_fit_score;
  const displayedFitScore = lastMatch?.fit_score ?? storedFitScore;
  const reasons = lastMatch ? summarizeReasons(lastMatch.match_reasons) : [];

  return (
    <Card className="overflow-hidden rounded-[1.5rem] border-border bg-card/95">
      <CardHeader>
        <CardTitle>{t("leadDetail.icp.title")}</CardTitle>
        <CardDescription>{t("leadDetail.icp.description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-muted/20 p-4">
          <div>
            <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
              {t("leadDetail.icp.fitScore")}
            </p>
            <p className="mt-2 text-2xl font-bold">
              {formatScore(displayedFitScore)}
            </p>
          </div>
          {lastMatch ? (
            <Badge tone={lastMatch.matched ? "success" : "neutral"}>
              {lastMatch.matched
                ? t("leadDetail.icp.matched")
                : t("leadDetail.icp.notMatched")}
            </Badge>
          ) : null}
        </div>

        {displayedFitScore === null || displayedFitScore === undefined ? (
          <EmptyState
            title={t("leadDetail.icp.noneTitle")}
            description={t("leadDetail.icp.noneDescription")}
          />
        ) : null}

        {profilesLoading ? (
          <QueryStateNotice
            tone="loading"
            title={t("leadDetail.icp.loadingProfiles")}
            description={t("leadDetail.icp.loadingProfilesDescription")}
          />
        ) : profilesError ? (
          <QueryStateNotice
            tone="error"
            title={t("leadDetail.icp.profileLoadError")}
            error={profilesError}
          />
        ) : profiles.length === 0 ? (
          <EmptyState
            title={t("leadDetail.icp.noProfilesTitle")}
            description={t("leadDetail.icp.noProfilesDescription")}
          />
        ) : (
          <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
            <Select value={selectedProfileId} onValueChange={onProfileChange}>
              <SelectTrigger className="h-11 rounded-xl bg-background/70 text-start">
                <SelectValue placeholder={t("leadDetail.icp.selectProfile")} />
              </SelectTrigger>
              <SelectContent>
                {profiles.map((profile) => (
                  <SelectItem key={profile.public_id} value={profile.public_id}>
                    {profile.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              onClick={onRecompute}
              disabled={!selectedProfileId || recomputing}
            >
              {recomputing
                ? t("leadDetail.icp.recomputing")
                : t("leadDetail.icp.recompute")}
            </Button>
          </div>
        )}

        {lastMatch ? (
          <div className="space-y-3 rounded-xl border border-border bg-muted/20 p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
              {t("leadDetail.icp.latestMatch")}
            </p>
            <p className="text-sm text-muted-foreground">
              {formatDate(lastMatch.calculated_at)}
            </p>
            {reasons.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {reasons.map((reason) => (
                  <Badge key={reason} tone="info" className="max-w-full">
                    <span className="truncate">{reason}</span>
                  </Badge>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function summarizeReasons(reasons: Record<string, unknown>) {
  return Object.entries(reasons)
    .flatMap(([key, value]) => reasonValueToLabels(key, value))
    .slice(0, 8);
}

function reasonValueToLabels(key: string, value: unknown): string[] {
  if (typeof value === "string" || typeof value === "number") {
    return [`${key}: ${String(value)}`];
  }
  if (typeof value === "boolean") {
    return [`${key}: ${value ? "yes" : "no"}`];
  }
  if (Array.isArray(value)) {
    return value.map((item) => `${key}: ${String(item)}`).slice(0, 4);
  }
  return [];
}
