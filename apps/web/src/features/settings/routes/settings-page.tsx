import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm, useWatch, type Control, type UseFormSetValue } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shell/page-header";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  activatePromptTemplate,
  activateScoringVersion,
  createPromptTemplate,
  createScoringVersion,
  getActiveScoringConfig,
  getOperationalHealth,
  getProviderSettings,
  getWorkspaceSettings,
  listAuditLogs,
  listPromptTemplates,
  listScoringVersions,
  updateWorkspaceSettings,
  updateProviderSettings,
} from "@/features/settings/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { formatDate } from "@/lib/presenters";

const providerSchema = z.object({
  hl: z.string().min(2).max(16),
  gl: z.string().min(2).max(16),
  google_domain: z.string().min(4).max(64),
  enrich_top_n: z.coerce.number().int().min(0).max(100),
});

const scoringSchema = z.object({
  local_trust: z.coerce.number().min(0).max(1),
  website_presence: z.coerce.number().min(0).max(1),
  search_visibility: z.coerce.number().min(0).max(1),
  opportunity: z.coerce.number().min(0).max(1),
  data_confidence: z.coerce.number().min(0).max(1),
  high_min: z.coerce.number().min(0).max(100),
  medium_min: z.coerce.number().min(0).max(100),
  low_min: z.coerce.number().min(0).max(100),
  confidence_min: z.coerce.number().min(0).max(1),
  note: z.string().max(255).optional(),
});

const promptTemplateSchema = z.object({
  name: z.string().min(1).max(255),
  template_text: z.string().min(1).max(16000),
  activate: z.boolean().default(true),
});

const workspaceSettingsSchema = z.object({
  name: z.string().min(2).max(255),
  slug: z.string().min(2).max(120),
});

type ProviderValues = z.infer<typeof providerSchema>;
type ScoringValues = z.infer<typeof scoringSchema>;
type PromptTemplateValues = z.infer<typeof promptTemplateSchema>;
type WorkspaceSettingsValues = z.infer<typeof workspaceSettingsSchema>;

export function SettingsPage() {
  const { t } = useTranslation();
  useDocumentTitle(t("settings.title"));
  const queryClient = useQueryClient();
  const [adminSuccess, setAdminSuccess] = useState<string | null>(null);
  const workspaceQuery = useQuery({
    queryKey: ["workspace-settings"],
    queryFn: getWorkspaceSettings,
  });
  const scoringQuery = useQuery({
    queryKey: ["admin", "scoring", "active"],
    queryFn: getActiveScoringConfig,
  });
  const versionsQuery = useQuery({
    queryKey: ["admin", "scoring", "versions"],
    queryFn: listScoringVersions,
  });
  const providerQuery = useQuery({
    queryKey: ["admin", "provider-settings"],
    queryFn: getProviderSettings,
  });
  const promptTemplatesQuery = useQuery({
    queryKey: ["admin", "prompt-templates"],
    queryFn: listPromptTemplates,
  });
  const healthQuery = useQuery({
    queryKey: ["admin", "operations", "health"],
    queryFn: getOperationalHealth,
  });
  const auditQuery = useQuery({
    queryKey: ["admin", "audit-logs"],
    queryFn: listAuditLogs,
  });

  const providerForm = useForm<ProviderValues>({
    resolver: zodResolver(providerSchema),
    defaultValues: {
      hl: "en",
      gl: "tr",
      google_domain: "google.com",
      enrich_top_n: 20,
    },
  });
  const scoringForm = useForm<ScoringValues>({
    resolver: zodResolver(scoringSchema),
    defaultValues: {
      local_trust: 0.25,
      website_presence: 0.25,
      search_visibility: 0.2,
      opportunity: 0.2,
      data_confidence: 0.1,
      high_min: 75,
      medium_min: 55,
      low_min: 35,
      confidence_min: 0.45,
      note: "",
    },
  });
  const promptTemplateForm = useForm<PromptTemplateValues>({
    resolver: zodResolver(promptTemplateSchema),
    defaultValues: {
      name: "",
      template_text: "",
      activate: true,
    },
  });
  const workspaceForm = useForm<WorkspaceSettingsValues>({
    resolver: zodResolver(workspaceSettingsSchema),
    defaultValues: {
      name: "",
      slug: "",
    },
  });

  useEffect(() => {
    if (workspaceQuery.data) {
      workspaceForm.reset({
        name: workspaceQuery.data.workspace.name,
        slug: workspaceQuery.data.workspace.slug,
      });
    }
  }, [workspaceForm, workspaceQuery.data]);

  useEffect(() => {
    if (providerQuery.data) {
      providerForm.reset(providerQuery.data);
    }
  }, [providerForm, providerQuery.data]);

  useEffect(() => {
    if (scoringQuery.data) {
      const active = scoringQuery.data.active_version;
      scoringForm.reset({
        ...active.weights,
        ...active.thresholds,
        note: active.note ?? "",
      });
    }
  }, [scoringForm, scoringQuery.data]);

  const refreshAdminQueries = () => {
    queryClient.invalidateQueries({ queryKey: ["admin"] });
  };

  const providerMutation = useMutation({
    mutationFn: updateProviderSettings,
    onSuccess: () => {
      refreshAdminQueries();
      setAdminSuccess(t("settings.providerSettingsSaved"));
    },
  });
  const workspaceMutation = useMutation({
    mutationFn: updateWorkspaceSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspace-settings"] });
      setAdminSuccess(t("settings.workspaceSettingsSaved"));
    },
  });
  const createVersionMutation = useMutation({
    mutationFn: createScoringVersion,
    onSuccess: () => {
      refreshAdminQueries();
      setAdminSuccess(t("settings.scoringVersionCreated"));
    },
  });
  const activateMutation = useMutation({
    mutationFn: activateScoringVersion,
    onSuccess: () => {
      refreshAdminQueries();
      setAdminSuccess(t("settings.scoringVersionActivated"));
    },
  });
  const createPromptTemplateMutation = useMutation({
    mutationFn: createPromptTemplate,
    onSuccess: () => {
      refreshAdminQueries();
      setAdminSuccess(t("settings.promptTemplateCreated"));
      promptTemplateForm.reset({
        name: "",
        template_text: "",
        activate: true,
      });
    },
  });
  const activatePromptTemplateMutation = useMutation({
    mutationFn: activatePromptTemplate,
    onSuccess: () => {
      refreshAdminQueries();
      setAdminSuccess(t("settings.promptTemplateActivated"));
    },
  });

  if (
    scoringQuery.isPending ||
    workspaceQuery.isPending ||
    providerQuery.isPending ||
    versionsQuery.isPending ||
    promptTemplatesQuery.isPending ||
    healthQuery.isPending ||
    auditQuery.isPending
  ) {
    return (
      <QueryStateNotice
        tone="loading"
        title={t("settings.loadingTitle")}
        description={t("settings.loadingDescription")}
      />
    );
  }

  if (
    scoringQuery.isError ||
    workspaceQuery.isError ||
    providerQuery.isError ||
    versionsQuery.isError ||
    promptTemplatesQuery.isError ||
    healthQuery.isError ||
    auditQuery.isError
  ) {
    return (
      <EmptyState
        title={t("settings.unavailableTitle")}
        description={t("settings.unavailableDescription")}
      />
    );
  }

  return (
    <div className="space-y-6 p-3 sm:p-4 lg:p-6">
      <PageHeader
        eyebrow={t("settings.eyebrow")}
        title={t("settings.headerTitle")}
        description={t("settings.headerDescription")}
      />

      <Card>
        <CardHeader>
          <CardTitle>{t("settings.workspaceProfile")}</CardTitle>
          <CardDescription>{t("settings.workspaceProfileDescription")}</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4 md:grid-cols-2" onSubmit={workspaceForm.handleSubmit((values) => workspaceMutation.mutate(values))}>
            <Field label={t("settings.workspaceName")}>
              <Input aria-label={t("settings.workspaceName")} {...workspaceForm.register("name")} />
            </Field>
            <Field label={t("settings.workspaceSlug")}>
              <Input aria-label={t("settings.workspaceSlug")} {...workspaceForm.register("slug")} />
            </Field>
            <div className="md:col-span-2 flex flex-wrap items-center gap-3">
              <Button type="submit" disabled={workspaceMutation.isPending}>
                {workspaceMutation.isPending ? t("common.saving") : t("settings.saveWorkspaceProfile")}
              </Button>
              {workspaceQuery.data ? (
                <span className="text-sm text-[color:var(--muted)]">
                  {t("settings.owner")}: {workspaceQuery.data.owner_user_public_id ?? t("leads.unassigned")} / {t("common.status")}: {workspaceQuery.data.workspace.status}
                </span>
              ) : null}
            </div>
          </form>
        </CardContent>
      </Card>

      {adminSuccess ? (
        <QueryStateNotice tone="success" title={t("settings.adminActionCompleted")} description={adminSuccess} />
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label={t("settings.failedJobs7d")} value={String(healthQuery.data?.failed_jobs_last_7_days ?? 0)} />
        <MetricCard
          label={t("settings.providerFailures7d")}
          value={String(healthQuery.data?.provider_failures_last_7_days ?? 0)}
        />
        <MetricCard label={t("settings.discoveryRuntime")} value={healthQuery.data?.discovery_runtime ?? t("common.unknown")} />
        <MetricCard label={t("settings.currentAiRuntime")} value={healthQuery.data?.current_ai_runtime ?? t("common.unknown")} />
      </div>

      <Tabs defaultValue="overview" className="space-y-0">
        <TabsList className="grid w-full grid-cols-1 gap-1 md:grid-cols-2 xl:grid-cols-5">
          <TabsTrigger value="overview" className="flex-col items-start gap-1 text-start md:items-center">
            <span className="font-semibold">{t("settings.systemOverview")}</span>
            <span className="text-xs text-[color:var(--muted)]">{t("settings.systemOverviewDescription")}</span>
          </TabsTrigger>
          <TabsTrigger value="provider" className="flex-col items-start gap-1 text-start md:items-center">
            <span className="font-semibold">{t("settings.providerSettings")}</span>
            <span className="text-xs text-[color:var(--muted)]">{t("settings.providerSettingsDescription")}</span>
          </TabsTrigger>
          <TabsTrigger value="scoring" className="flex-col items-start gap-1 text-start md:items-center">
            <span className="font-semibold">{t("settings.scoringConfig")}</span>
            <span className="text-xs text-[color:var(--muted)]">{t("settings.scoringConfigDescription")}</span>
          </TabsTrigger>
          <TabsTrigger value="prompts" className="flex-col items-start gap-1 text-start md:items-center">
            <span className="font-semibold">{t("settings.promptTemplates")}</span>
            <span className="text-xs text-[color:var(--muted)]">{t("settings.promptTemplatesDescription")}</span>
          </TabsTrigger>
          <TabsTrigger value="audit" className="flex-col items-start gap-1 text-start md:items-center">
            <span className="font-semibold">{t("settings.audit")}</span>
            <span className="text-xs text-[color:var(--muted)]">{t("settings.auditDescription")}</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
            <div className="grid gap-4 2xl:grid-cols-[0.8fr_1.2fr]">
            <Card className="min-w-0">
              <CardHeader>
                <CardTitle>{t("settings.operationalHealth")}</CardTitle>
                <CardDescription>{t("settings.operationalHealthDescription")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <StatusMetric
                    label={t("settings.database")}
                    ok={healthQuery.data?.database_ok ?? false}
                    okLabel={t("settings.healthy")}
                    badLabel={t("settings.unavailable")}
                  />
                  <StatusMetric
                    label="SerpAPI"
                    ok={healthQuery.data?.serpapi_live_reachable ?? false}
                    okLabel={t("settings.reachable")}
                    badLabel={t("settings.unavailable")}
                  />
                  <StatusMetric
                    label="Ollama"
                    ok={healthQuery.data?.ollama_reachable ?? false}
                    okLabel={t("settings.reachable")}
                    badLabel={t("settings.unavailable")}
                  />
                  <StatusMetric
                    label={t("settings.openaiFallback")}
                    ok={healthQuery.data?.openai_fallback_configured ?? false}
                    okLabel={t("settings.configured")}
                    badLabel={t("settings.missingKey")}
                  />
                  <MetricCard
                    label={t("settings.failedJobs7d")}
                    value={String(healthQuery.data?.failed_jobs_last_7_days ?? 0)}
                  />
                  <MetricCard
                    label={t("settings.providerFailures7d")}
                    value={String(healthQuery.data?.provider_failures_last_7_days ?? 0)}
                  />
                  <MetricCard
                    label={t("settings.serpapiMode")}
                    value={healthQuery.data?.serpapi_runtime_mode ?? "unknown"}
                  />
                  <MetricCard
                    label={t("settings.discoveryRuntime")}
                    value={healthQuery.data?.discovery_runtime ?? t("common.unknown")}
                  />
                  <MetricCard label={t("settings.currentAiRuntime")} value={healthQuery.data?.current_ai_runtime ?? t("common.unknown")} />
                  <MetricCard label={t("settings.aiFallbackRuntime")} value={healthQuery.data?.analysis_fallback_runtime ?? t("common.none")} />
                </div>
                {(healthQuery.data?.runtime_warnings ?? []).length ? (
                  <div className="space-y-2">
                    <p className="text-sm font-semibold">{t("settings.runtimeWarnings")}</p>
                    {(healthQuery.data?.runtime_warnings ?? []).map((warning) => (
                      <QueryStateNotice
                        key={warning}
                        tone="info"
                        title={t("settings.environmentWarning")}
                        description={warning}
                      />
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    title={t("settings.noRuntimeWarnings")}
                    description={t("settings.noRuntimeWarningsDescription")}
                  />
                )}
              </CardContent>
            </Card>

            <div className="space-y-4">
              <Card className="min-w-0">
                <CardHeader>
                  <CardTitle>{t("settings.recentFailedJobs")}</CardTitle>
                  <CardDescription>{t("settings.recentFailedJobsDescription")}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {(healthQuery.data?.recent_failed_jobs ?? []).length === 0 ? (
                    <EmptyState
                      title={t("settings.noFailedJobs")}
                      description={t("settings.noFailedJobsDescription")}
                    />
                  ) : (
                    healthQuery.data?.recent_failed_jobs.map((job) => (
                      <div key={job.public_id} className="rounded-xl border border-[color:var(--border)] p-4">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="font-semibold">
                              {job.business_type} / {job.city}
                            </p>
                            <p className="mt-1 text-sm text-[color:var(--muted)]">
                              {t("settings.providerErrorsCount", { count: job.provider_error_count })}
                            </p>
                          </div>
                          <div className="text-end text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">
                            <p>{job.status}</p>
                            <p className="mt-1">{formatDate(job.finished_at ?? job.queued_at)}</p>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>

              <Card className="min-w-0">
                <CardHeader>
                  <CardTitle>{t("settings.recentProviderFailures")}</CardTitle>
                  <CardDescription>{t("settings.recentProviderFailuresDescription")}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {(healthQuery.data?.recent_provider_failures ?? []).length === 0 ? (
                    <EmptyState
                      title={t("settings.noProviderFailures")}
                      description={t("settings.noProviderFailuresDescription")}
                    />
                  ) : (
                    healthQuery.data?.recent_provider_failures.map((failure) => (
                      <div key={failure.public_id} className="rounded-xl border border-[color:var(--border)] p-4">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="font-semibold">
                              {failure.engine} / {failure.mode}
                            </p>
                            <p className="mt-1 text-sm text-[color:var(--muted)]">
                              {failure.error_message ?? t("settings.providerFailureNoMessage")}
                            </p>
                          </div>
                          <div className="text-end text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">
                            <p>{failure.status}</p>
                            <p className="mt-1">{formatDate(failure.finished_at ?? failure.started_at)}</p>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="provider" className="space-y-4">
          <div className="grid gap-4 2xl:grid-cols-[0.72fr_1.28fr]">
            <Card className="min-w-0">
              <CardHeader>
                <CardTitle>{t("settings.providerRuntimeProfile")}</CardTitle>
                <CardDescription>{t("settings.providerRuntimeProfileDescription")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <MetricCard label={t("settings.serpapiMode")} value={healthQuery.data?.serpapi_runtime_mode ?? t("common.unknown")} />
                <MetricCard label={t("settings.discoveryRuntime")} value={healthQuery.data?.discovery_runtime ?? t("common.unknown")} />
                <MetricCard label={t("settings.currentAiRuntime")} value={healthQuery.data?.current_ai_runtime ?? t("common.unknown")} />
                <StatusMetric
                  label={t("settings.serpapiAvailability")}
                  ok={healthQuery.data?.serpapi_live_reachable ?? false}
                  okLabel={t("settings.reachable")}
                  badLabel={t("settings.unavailable")}
                />
              </CardContent>
            </Card>

            <Card className="min-w-0">
              <CardHeader>
                <CardTitle>{t("settings.providerDefaults")}</CardTitle>
                <CardDescription>{t("settings.providerDefaultsDescription")}</CardDescription>
              </CardHeader>
              <CardContent>
                <form className="space-y-4" onSubmit={providerForm.handleSubmit((values) => providerMutation.mutate(values))}>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Field label={t("settings.languageHl")}>
                      <Input aria-label={t("settings.languageHl")} {...providerForm.register("hl")} />
                    </Field>
                    <Field label={t("settings.geoGl")}>
                      <Input aria-label={t("settings.geoGl")} {...providerForm.register("gl")} />
                    </Field>
                    <Field label={t("settings.googleDomain")}>
                      <Input aria-label={t("settings.googleDomain")} {...providerForm.register("google_domain")} />
                    </Field>
                    <Field label={t("settings.enrichTopN")}>
                      <Input aria-label={t("settings.enrichTopN")} type="number" {...providerForm.register("enrich_top_n")} />
                    </Field>
                  </div>
                  <Button type="submit" disabled={providerMutation.isPending}>
                    {providerMutation.isPending ? t("common.saving") : t("settings.saveProviderSettings")}
                  </Button>
                  {providerMutation.isError ? (
                    <QueryStateNotice
                      tone="error"
                      title={t("settings.providerSettingsNotSaved")}
                      description={providerMutation.error.message}
                    />
                  ) : null}
                </form>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="scoring" className="space-y-4">
          <Card className="min-w-0">
            <CardHeader>
              <CardTitle>{t("settings.scoringConfiguration")}</CardTitle>
              <CardDescription>{t("settings.scoringConfigurationDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {scoringQuery.data ? (
                <div className="rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">{t("settings.activeVersion")}</p>
                  <p className="mt-2 text-lg font-bold">{scoringQuery.data.active_version.public_id}</p>
                  <p className="mt-2 text-sm text-[color:var(--muted)]">
                    {t("settings.created")} {formatDate(scoringQuery.data.active_version.created_at)} {t("settings.by")}{" "}
                    {scoringQuery.data.active_version.created_by_user_public_id}
                  </p>
                </div>
              ) : null}

              <div className="grid gap-4 2xl:grid-cols-[1.05fr_0.95fr]">
                <form
                  className="space-y-4"
                  onSubmit={scoringForm.handleSubmit((values) =>
                    createVersionMutation.mutate({
                      weights: {
                        local_trust: values.local_trust,
                        website_presence: values.website_presence,
                        search_visibility: values.search_visibility,
                        opportunity: values.opportunity,
                        data_confidence: values.data_confidence,
                      },
                      thresholds: {
                        high_min: values.high_min,
                        medium_min: values.medium_min,
                        low_min: values.low_min,
                        confidence_min: values.confidence_min,
                      },
                      note: values.note,
                    }),
                  )}
                >
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="local_trust">
                      <Input aria-label="local_trust" type="number" step="0.01" {...scoringForm.register("local_trust")} />
                    </Field>
                    <Field label="website_presence">
                      <Input aria-label="website_presence" type="number" step="0.01" {...scoringForm.register("website_presence")} />
                    </Field>
                    <Field label="search_visibility">
                      <Input aria-label="search_visibility" type="number" step="0.01" {...scoringForm.register("search_visibility")} />
                    </Field>
                    <Field label="opportunity">
                      <Input aria-label="opportunity" type="number" step="0.01" {...scoringForm.register("opportunity")} />
                    </Field>
                    <Field label="data_confidence">
                      <Input aria-label="data_confidence" type="number" step="0.01" {...scoringForm.register("data_confidence")} />
                    </Field>
                    <Field label="high_min">
                      <Input aria-label="high_min" type="number" step="0.01" {...scoringForm.register("high_min")} />
                    </Field>
                    <Field label="medium_min">
                      <Input aria-label="medium_min" type="number" step="0.01" {...scoringForm.register("medium_min")} />
                    </Field>
                    <Field label="low_min">
                      <Input aria-label="low_min" type="number" step="0.01" {...scoringForm.register("low_min")} />
                    </Field>
                    <Field label="confidence_min">
                      <Input aria-label="confidence_min" type="number" step="0.01" {...scoringForm.register("confidence_min")} />
                    </Field>
                  </div>
                  <Field label={t("settings.versionNote")}>
                    <Textarea aria-label={t("settings.versionNote")} {...scoringForm.register("note")} />
                  </Field>
                  <Button type="submit" disabled={createVersionMutation.isPending}>
                    {createVersionMutation.isPending ? t("common.creating") : t("settings.createScoringVersion")}
                  </Button>
                  {createVersionMutation.isError ? (
                    <QueryStateNotice
                      tone="error"
                      title={t("settings.scoringVersionNotCreated")}
                      description={createVersionMutation.error.message}
                    />
                  ) : null}
                </form>

                <div className="space-y-3">
                  {activateMutation.isError ? (
                    <QueryStateNotice
                      tone="error"
                      title={t("settings.couldNotActivateScoring")}
                      description={activateMutation.error.message}
                    />
                  ) : null}

                  {(versionsQuery.data?.items ?? []).length === 0 ? (
                    <EmptyState
                      title={t("settings.noScoringVersions")}
                      description={t("settings.noScoringVersionsDescription")}
                    />
                  ) : (
                    (versionsQuery.data?.items ?? []).map((version) => (
                      <div key={version.public_id} className="rounded-xl border border-[color:var(--border)] p-4">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="font-semibold">{version.public_id}</p>
                            <p className="mt-1 text-sm text-[color:var(--muted)]">{version.note ?? t("settings.noNote")}</p>
                          </div>
                          <Button
                            variant="secondary"
                            disabled={
                              activateMutation.isPending || scoringQuery.data?.active_version.public_id === version.public_id
                            }
                            onClick={() => activateMutation.mutate(version.public_id)}
                          >
                            {scoringQuery.data?.active_version.public_id === version.public_id ? t("common.active") : t("common.activate")}
                          </Button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="prompts" className="space-y-4">
          <Card className="min-w-0">
            <CardHeader>
              <CardTitle>{t("settings.promptTemplates")}</CardTitle>
              <CardDescription>{t("settings.promptTemplatesCardDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4 2xl:grid-cols-[0.95fr_1.05fr]">
                <form
                  className="space-y-4"
                  onSubmit={promptTemplateForm.handleSubmit((values) => createPromptTemplateMutation.mutate(values))}
                >
                  <Field label={t("settings.templateName")}>
                    <Input aria-label={t("settings.templateName")} {...promptTemplateForm.register("name")} />
                  </Field>
                  <Field label={t("settings.templateText")}>
                    <Textarea
                      aria-label={t("settings.templateText")}
                      className="min-h-[180px]"
                      {...promptTemplateForm.register("template_text")}
                    />
                  </Field>
                  <PromptTemplateActivateField
                    control={promptTemplateForm.control}
                    setValue={promptTemplateForm.setValue}
                  />
                  <Button type="submit" disabled={createPromptTemplateMutation.isPending}>
                    {createPromptTemplateMutation.isPending ? t("common.creating") : t("settings.createPromptTemplate")}
                  </Button>
                  {createPromptTemplateMutation.isError ? (
                    <QueryStateNotice
                      tone="error"
                      title={t("settings.promptTemplateNotCreated")}
                      description={createPromptTemplateMutation.error.message}
                    />
                  ) : null}
                </form>

                <div className="space-y-3">
                  {activatePromptTemplateMutation.isError ? (
                    <QueryStateNotice
                      tone="error"
                      title={t("settings.couldNotActivatePrompt")}
                      description={activatePromptTemplateMutation.error.message}
                    />
                  ) : null}

                  {(promptTemplatesQuery.data?.items ?? []).length === 0 ? (
                    <EmptyState
                      title={t("settings.noPromptTemplates")}
                      description={t("settings.noPromptTemplatesDescription")}
                    />
                  ) : (
                    (promptTemplatesQuery.data?.items ?? []).map((template) => (
                      <div key={template.public_id} className="rounded-xl border border-[color:var(--border)] p-4">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div className="space-y-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="font-semibold">{template.name}</p>
                              <Badge tone={template.is_active ? "success" : "neutral"}>
                                {template.is_active ? t("common.active") : t("common.inactive")}
                              </Badge>
                            </div>
                            <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">
                              {template.public_id} / {formatDate(template.created_at)}
                            </p>
                          </div>
                          <Button
                            variant="secondary"
                            disabled={activatePromptTemplateMutation.isPending || template.is_active}
                            onClick={() => activatePromptTemplateMutation.mutate(template.public_id)}
                          >
                            {template.is_active ? t("common.active") : t("common.activate")}
                          </Button>
                        </div>
                        <pre className="mt-3 overflow-x-auto rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-3 text-xs leading-6 text-[color:var(--muted)]">
                          {template.template_text}
                        </pre>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="audit" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{t("settings.auditLog")}</CardTitle>
              <CardDescription>{t("settings.auditLogDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {(auditQuery.data?.items ?? []).length === 0 ? (
                <EmptyState
                  title={t("settings.noAuditEntries")}
                  description={t("settings.noAuditEntriesDescription")}
                />
              ) : (
                auditQuery.data?.items.map((entry) => (
                  <div key={entry.public_id} className="rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold">{entry.event_name}</p>
                        <p className="mt-1 text-sm text-[color:var(--muted)]">{entry.details}</p>
                      </div>
                      <div className="text-end text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">
                        <p>{entry.actor_user_public_id ?? t("common.system")}</p>
                        <p className="mt-1">{formatDate(entry.created_at)}</p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.02)]">
      <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">{label}</p>
      <p className="mt-2 text-xl font-bold">{value}</p>
    </div>
  );
}

function StatusMetric({
  label,
  ok,
  okLabel,
  badLabel,
}: {
  label: string;
  ok: boolean;
  okLabel: string;
  badLabel: string;
}) {
  return (
    <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.02)]">
      <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">{label}</p>
      <div className="mt-3">
        <Badge tone={ok ? "success" : "danger"}>{ok ? okLabel : badLabel}</Badge>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0 space-y-2">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function PromptTemplateActivateField({
  control,
  setValue,
}: {
  control: Control<PromptTemplateValues>;
  setValue: UseFormSetValue<PromptTemplateValues>;
}) {
  const { t } = useTranslation();
  const activate = useWatch({
    control,
    name: "activate",
  });

  return (
    <label className="flex items-center gap-3 rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] px-3 py-3 text-sm font-medium">
      <Checkbox
        checked={activate}
        onCheckedChange={(checked) => setValue("activate", checked === true, { shouldDirty: true })}
      />
      {t("settings.activateImmediately")}
    </label>
  );
}
