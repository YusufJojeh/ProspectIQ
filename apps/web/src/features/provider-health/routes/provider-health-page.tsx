import { useQuery } from "@tanstack/react-query";
import { Clock3, RadioTower } from "lucide-react";
import { useTranslation } from "react-i18next";
import { EmptyState } from "@/components/shared/empty-state";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { PageHeader } from "@/components/shell/page-header";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getOperationalHealth } from "@/features/settings/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { formatDate } from "@/lib/presenters";

export function ProviderHealthPage() {
  const { t } = useTranslation();
  useDocumentTitle(t("providerHealth.title"));

  const healthQuery = useQuery({
    queryKey: ["provider-health", "operations"],
    queryFn: getOperationalHealth,
  });

  if (healthQuery.isPending) {
    return (
      <QueryStateNotice
        tone="loading"
        title={t("providerHealth.loadingTitle")}
        description={t("providerHealth.loadingDescription")}
      />
    );
  }

  if (healthQuery.isError) {
    return (
      <EmptyState
        title={t("providerHealth.unavailableTitle")}
        description={healthQuery.error.message}
      />
    );
  }

  const health = healthQuery.data;
  const providers = [
    {
      name: "Tavily",
      configured: health.tavily_configured,
      status: health.tavily_runtime_mode,
      detail: t("providerHealth.tavilyDetail", {
        maxResults: health.tavily_max_results,
        maxCalls: health.tavily_live_max_calls,
      }),
    },
    {
      name: "SerpAPI",
      configured: health.serpapi_configured,
      status: health.serpapi_runtime_mode,
      detail: health.serpapi_live_reachable
        ? t("providerHealth.reachable")
        : t("providerHealth.notReachable"),
    },
    {
      name: "OpenAI",
      configured: health.openai_configured,
      status: health.openai_fallback_configured
        ? t("providerHealth.fallbackReady")
        : health.current_ai_runtime,
      detail: t("providerHealth.openaiDetail", {
        runtime: health.current_ai_runtime,
      }),
    },
  ];

  return (
    <div className="space-y-6 p-3 sm:p-4 lg:p-6">
      <PageHeader
        eyebrow={t("providerHealth.eyebrow")}
        title={t("providerHealth.title")}
        description={t("providerHealth.description")}
      />

      <section className="grid gap-4 md:grid-cols-3">
        {providers.map((provider) => (
          <Card key={provider.name} className="rounded-[1.5rem] border-border bg-card/95">
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle>{provider.name}</CardTitle>
                  <CardDescription>{provider.detail}</CardDescription>
                </div>
                <Badge tone={provider.configured ? "success" : "warning"}>
                  {provider.configured
                    ? t("providerHealth.configured")
                    : t("providerHealth.notConfigured")}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2 rounded-2xl border border-border bg-muted/20 px-4 py-3 text-sm">
                <RadioTower className="size-4 text-muted-foreground" />
                <span className="text-muted-foreground">
                  {t("providerHealth.runtime")}:
                </span>
                <span className="font-semibold text-foreground">{provider.status}</span>
              </div>
            </CardContent>
          </Card>
        ))}
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="rounded-[1.5rem] border-border bg-card/95">
          <CardHeader>
            <CardTitle>{t("providerHealth.discoveryRuntime")}</CardTitle>
            <CardDescription>
              {t("providerHealth.discoveryRuntimeDescription")}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm">
            <StatusRow
              label={t("providerHealth.executionMode")}
              value={health.discovery_execution_mode}
              tone="info"
            />
            <StatusRow
              label={t("providerHealth.discoveryRuntime")}
              value={health.discovery_runtime}
              tone={health.discovery_runtime === "blocked" ? "warning" : "success"}
            />
            <StatusRow
              label={t("providerHealth.providerFailures7d")}
              value={String(health.provider_failures_last_7_days)}
              tone={health.provider_failures_last_7_days > 0 ? "warning" : "success"}
            />
          </CardContent>
        </Card>

        <Card className="rounded-[1.5rem] border-border bg-card/95">
          <CardHeader>
            <CardTitle>{t("providerHealth.runtimeWarnings")}</CardTitle>
            <CardDescription>
              {t("providerHealth.runtimeWarningsDescription")}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {health.runtime_warnings.length ? (
              <div className="space-y-2">
                {health.runtime_warnings.map((warning) => (
                  <div
                    key={warning}
                    className="rounded-2xl border border-border bg-muted/20 px-4 py-3 text-sm text-muted-foreground"
                  >
                    {warning}
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title={t("providerHealth.noWarnings")}
                description={t("providerHealth.noWarningsDescription")}
              />
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="rounded-[1.5rem] border-border bg-card/95">
        <CardHeader>
          <CardTitle>{t("providerHealth.recentFailures")}</CardTitle>
          <CardDescription>
            {t("providerHealth.recentFailuresDescription")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {health.recent_provider_failures.length ? (
            <div className="space-y-3">
              {health.recent_provider_failures.map((failure) => (
                <div
                  key={`${failure.provider}-${failure.engine}-${failure.started_at}`}
                  className="grid gap-3 rounded-2xl border border-border bg-muted/20 p-4 md:grid-cols-[1fr_auto]"
                >
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold capitalize">{failure.provider}</p>
                      <Badge tone={providerStatusTone(failure.status)}>
                        {failure.status}
                      </Badge>
                      {failure.http_status ? (
                        <Badge tone="neutral">HTTP {failure.http_status}</Badge>
                      ) : null}
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {failure.engine} / {failure.mode}
                    </p>
                    <p className="mt-2 text-sm text-muted-foreground">
                      {safeProviderMessage(failure.error_message, t)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Clock3 className="size-4" />
                    {formatDate(failure.started_at)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title={t("providerHealth.noRecentFailures")}
              description={t("providerHealth.noRecentFailuresDescription")}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatusRow({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: BadgeTone;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-2xl border border-border bg-muted/20 px-4 py-3">
      <span className="text-muted-foreground">{label}</span>
      <Badge tone={tone}>{value}</Badge>
    </div>
  );
}

function providerStatusTone(status: string): BadgeTone {
  if (status === "ok") return "success";
  if (status === "rate_limited") return "warning";
  if (status === "timeout") return "caution";
  if (status === "error") return "error";
  return "neutral";
}

function safeProviderMessage(
  message: string | null,
  t: (key: string) => string,
): string {
  if (!message) {
    return t("providerHealth.noStoredMessage");
  }

  const normalized = message.replace(/\s+/g, " ").trim();
  const sensitivePattern = /(api[_ -]?key|authorization|bearer|sk-|traceback|stack trace)/i;
  if (!normalized || sensitivePattern.test(normalized)) {
    return t("providerHealth.redactedMessage");
  }

  return normalized.length > 180 ? `${normalized.slice(0, 177)}...` : normalized;
}
