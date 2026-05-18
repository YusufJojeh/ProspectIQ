import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  ShieldCheck,
  Zap,
  Settings,
  Activity,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Loader2,
  Database,
  FileText,
} from "lucide-react";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import {
  getActiveScoringConfig,
  getOperationalHealth,
  getProviderSettings,
  listScoringVersions,
  listPromptTemplates,
  activateScoringVersion,
  activatePromptTemplate,
} from "@/features/settings/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { cn } from "@/lib/utils";

export function AdminPage() {
  const { t } = useTranslation();
  useDocumentTitle(t("admin.title"));
  const queryClient = useQueryClient();

  const healthQuery = useQuery({
    queryKey: ["admin", "health"],
    queryFn: getOperationalHealth,
    refetchInterval: 30_000,
  });

  const scoringQuery = useQuery({
    queryKey: ["admin", "scoring-config"],
    queryFn: getActiveScoringConfig,
  });

  const versionsQuery = useQuery({
    queryKey: ["admin", "scoring-versions"],
    queryFn: listScoringVersions,
  });

  const providerQuery = useQuery({
    queryKey: ["admin", "provider-settings"],
    queryFn: getProviderSettings,
  });

  const promptsQuery = useQuery({
    queryKey: ["admin", "prompt-templates"],
    queryFn: listPromptTemplates,
  });

  const activateVersionMutation = useMutation({
    mutationFn: activateScoringVersion,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "scoring-config"] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "scoring-versions"] });
    },
  });

  const activatePromptMutation = useMutation({
    mutationFn: activatePromptTemplate,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "prompt-templates"] });
    },
  });

  const health = healthQuery.data;
  const isHealthy =
    health?.database_ok &&
    health?.serpapi_live_reachable &&
    health?.ollama_reachable &&
    health?.failed_jobs_last_7_days === 0;

  return (
    <div>
      <PageHeader
        eyebrow={t("admin.title")}
        title={t("admin.workspaceAdministration")}
        description={t("admin.workspaceAdministrationDescription")}
        actions={
          <Button
            size="sm"
            variant="outline"
            className="bg-transparent"
            onClick={() => void queryClient.invalidateQueries({ queryKey: ["admin"] })}
          >
            <RefreshCw className="size-3.5" /> {t("common.refresh")}
          </Button>
        }
      />

      <div className="p-3 sm:p-4 lg:p-6">
        {/* Health banner */}
        {healthQuery.isSuccess && (
          <div
            className={cn(
              "mb-4 flex items-center gap-3 rounded-xl border px-4 py-3 text-[12.5px]",
              isHealthy
                ? "border-[oklch(var(--evidence)/0.3)] bg-[oklch(var(--evidence)/0.08)] text-[oklch(var(--evidence))]"
                : "border-[oklch(var(--caution)/0.3)] bg-[oklch(var(--caution)/0.08)] text-[oklch(var(--caution))]",
            )}
          >
            {isHealthy ? <CheckCircle2 className="size-4 shrink-0" /> : <AlertTriangle className="size-4 shrink-0" />}
            <div>
              <span className="font-medium">{isHealthy ? t("admin.allSystemsOperational") : t("admin.degradedService")}</span>
              <span className="ms-2 text-muted-foreground">
                SerpAPI: {health?.serpapi_live_reachable ? t("admin.ok") : t("admin.down")} · Ollama: {health?.ollama_reachable ? t("admin.ok") : t("admin.down")} · DB:{" "}
                {health?.database_ok ? t("admin.ok") : t("admin.down")} · {t("admin.mode")}:{" "}
                {health?.discovery_runtime}
              </span>
            </div>
          </div>
        )}

        <Tabs defaultValue="scoring">
          <TabsList className="mb-4">
            <TabsTrigger value="scoring">
              <Settings className="me-1.5 size-3.5" /> {t("admin.scoringConfig")}
            </TabsTrigger>
            <TabsTrigger value="providers">
              <Zap className="me-1.5 size-3.5" /> {t("admin.providers")}
            </TabsTrigger>
            <TabsTrigger value="prompts">
              <FileText className="me-1.5 size-3.5" /> {t("admin.prompts")}
            </TabsTrigger>
            <TabsTrigger value="health">
              <Activity className="me-1.5 size-3.5" /> {t("admin.health")}
            </TabsTrigger>
          </TabsList>

          {/* ─── Scoring tab ─── */}
          <TabsContent value="scoring" className="grid gap-4">
            {scoringQuery.isPending && (
              <QueryStateNotice tone="loading" title={t("admin.loadingScoringTitle")} description={t("admin.fetchingConfiguration")} />
            )}
            {scoringQuery.isSuccess && (
              <div className="rounded-xl border border-border bg-card p-4">
                <div className="mb-3 flex items-center gap-2 text-[11.5px] font-medium uppercase tracking-wider text-muted-foreground">
                  <ShieldCheck className="size-3.5 text-[oklch(var(--evidence))]" />
                  {t("admin.activeScoringConfiguration")}
                </div>
                <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {Object.entries(scoringQuery.data.active_version.weights).map(([k, v]) => (
                    <div key={k} className="rounded-lg border border-border bg-muted/20 p-3">
                      <dt className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                        {k.replace(/_/g, " ")}
                      </dt>
                      <dd className="mt-1 font-mono text-[18px] font-semibold tabular-nums text-[oklch(var(--signal))]">
                        {(v as number).toFixed(2)}
                      </dd>
                    </div>
                  ))}
                </dl>
                <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  {Object.entries(scoringQuery.data.active_version.thresholds).map(([k, v]) => (
                    <div key={k} className="rounded-lg border border-border bg-muted/20 p-3">
                      <dt className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                        {k.replace(/_/g, " ")}
                      </dt>
                      <dd className="mt-1 font-mono text-[16px] font-semibold tabular-nums">{v as number}</dd>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {versionsQuery.isSuccess && (
              <div className="rounded-xl border border-border bg-card">
                <header className="border-b border-border px-4 py-3">
                  <div className="text-[12.5px] font-medium">{t("admin.versionHistory")}</div>
                </header>
                <ul className="divide-y divide-border">
                  {versionsQuery.data.items.map((v) => (
                    <li key={v.public_id} className="flex items-center gap-3 px-4 py-3">
                      <Database className="size-3.5 shrink-0 text-muted-foreground" />
                      <div className="min-w-0 flex-1">
                        <div className="text-[12.5px] font-medium">{v.note ?? t("admin.versionWithId", { id: v.public_id.slice(0, 8) })}</div>
                        <div className="font-mono text-[11px] text-muted-foreground">{v.public_id}</div>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 bg-transparent text-[11.5px]"
                        onClick={() => activateVersionMutation.mutate(v.public_id)}
                        disabled={activateVersionMutation.isPending}
                      >
                        {activateVersionMutation.isPending ? (
                          <Loader2 className="size-3 animate-spin" />
                        ) : null}
                        {t("common.activate")}
                      </Button>
                    </li>
                  ))}
                  {versionsQuery.data.items.length === 0 && (
                    <li className="px-4 py-6 text-center text-[12px] text-muted-foreground">
                      {t("admin.noScoringVersions")}
                    </li>
                  )}
                </ul>
              </div>
            )}
          </TabsContent>

          {/* ─── Providers tab ─── */}
          <TabsContent value="providers">
            {providerQuery.isPending && (
              <QueryStateNotice tone="loading" title={t("admin.loadingProviderTitle")} description={t("admin.fetchingConfiguration")} />
            )}
            {providerQuery.isSuccess && (
              <div className="rounded-xl border border-border bg-card p-4">
                <div className="mb-3 flex items-center gap-2 text-[11.5px] font-medium uppercase tracking-wider text-muted-foreground">
                  <Zap className="size-3.5 text-[oklch(var(--signal))]" />
                  {t("admin.providerConfiguration")}
                </div>
                <dl className="grid grid-cols-1 gap-3 xl:grid-cols-2">
                  {Object.entries(providerQuery.data).map(([k, v]) => (
                    <div key={k} className="rounded-lg border border-border bg-muted/20 p-3">
                      <dt className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                        {k.replace(/_/g, " ")}
                      </dt>
                      <dd className="mt-1 font-mono text-[12.5px] text-foreground">{String(v)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}
          </TabsContent>

          {/* ─── Prompts tab ─── */}
          <TabsContent value="prompts">
            {promptsQuery.isPending && (
              <QueryStateNotice tone="loading" title={t("admin.loadingPromptsTitle")} description={t("admin.fetchingTemplates")} />
            )}
            {promptsQuery.isSuccess && (
              <div className="rounded-xl border border-border bg-card">
                <header className="border-b border-border px-4 py-3">
                  <div className="text-[12.5px] font-medium">{t("admin.promptTemplates")}</div>
                </header>
                <ul className="divide-y divide-border">
                  {promptsQuery.data.items.map((pt) => (
                    <li key={pt.public_id} className="flex items-start gap-3 px-4 py-3">
                      <FileText className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-[12.5px] font-medium">{pt.name}</span>
                          {pt.is_active && (
                            <span className="inline-flex items-center rounded-full border border-[oklch(var(--evidence)/0.3)] bg-[oklch(var(--evidence)/0.08)] px-1.5 py-0.5 font-mono text-[10px] uppercase text-[oklch(var(--evidence))]">
                              {t("common.active")}
                            </span>
                          )}
                        </div>
                        <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">{pt.public_id}</div>
                      </div>
                      {!pt.is_active && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 bg-transparent text-[11.5px]"
                          onClick={() => activatePromptMutation.mutate(pt.public_id)}
                          disabled={activatePromptMutation.isPending}
                        >
                          {t("common.activate")}
                        </Button>
                      )}
                    </li>
                  ))}
                  {promptsQuery.data.items.length === 0 && (
                    <li className="px-4 py-6 text-center text-[12px] text-muted-foreground">
                      {t("admin.noPromptTemplates")}
                    </li>
                  )}
                </ul>
              </div>
            )}
          </TabsContent>

          {/* ─── Health tab ─── */}
          <TabsContent value="health">
            {healthQuery.isPending && (
              <QueryStateNotice tone="loading" title={t("admin.checkingHealthTitle")} description={t("admin.pingingServices")} />
            )}
            {healthQuery.isSuccess && (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {[
                  { k: "SerpAPI", ok: health!.serpapi_live_reachable, desc: t("admin.modeValue", { mode: health!.discovery_runtime }) },
                  { k: "Ollama", ok: health!.ollama_reachable, desc: t("admin.primaryRuntimeValue", { runtime: health!.current_ai_runtime }) },
                  { k: "OpenAI fallback", ok: health!.openai_fallback_configured, desc: health!.openai_fallback_configured ? t("admin.configured") : t("admin.notConfigured") },
                  { k: t("admin.dbStatus"), ok: health!.database_ok, desc: t("admin.persistenceLayer") },
                ].map((s) => (
                  <div
                    key={s.k}
                    className={cn(
                      "flex flex-col gap-2 rounded-xl border p-4",
                      s.ok
                        ? "border-[oklch(var(--evidence)/0.25)] bg-[oklch(var(--evidence)/0.05)]"
                        : "border-[oklch(var(--risk)/0.25)] bg-[oklch(var(--risk)/0.05)]",
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[13px] font-medium">{s.k}</span>
                      {s.ok ? (
                        <CheckCircle2 className="size-4 text-[oklch(var(--evidence))]" />
                      ) : (
                        <AlertTriangle className="size-4 text-[oklch(var(--risk))]" />
                      )}
                    </div>
                    <div className="text-[11.5px] text-muted-foreground">{s.desc}</div>
                    <div
                      className={cn(
                        "font-mono text-[11px] uppercase tracking-wider",
                        s.ok ? "text-[oklch(var(--evidence))]" : "text-[oklch(var(--risk))]",
                      )}
                    >
                      {s.ok ? t("admin.operational") : t("admin.degraded")}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
