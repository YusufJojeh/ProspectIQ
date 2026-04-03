import type { ReactNode } from "react";
import { useEffect } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  activateScoringVersion,
  createScoringVersion,
  getActiveScoringConfig,
  getProviderSettings,
  listAuditLogs,
  listScoringVersions,
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

type ProviderValues = z.infer<typeof providerSchema>;
type ScoringValues = z.infer<typeof scoringSchema>;

export function SettingsPage() {
  useDocumentTitle("Admin");
  const queryClient = useQueryClient();
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
    onSuccess: refreshAdminQueries,
  });
  const createVersionMutation = useMutation({
    mutationFn: createScoringVersion,
    onSuccess: refreshAdminQueries,
  });
  const activateMutation = useMutation({
    mutationFn: activateScoringVersion,
    onSuccess: refreshAdminQueries,
  });

  if (scoringQuery.isError || providerQuery.isError || versionsQuery.isError || auditQuery.isError) {
    return (
      <EmptyState
        title="Admin configuration is unavailable"
        description="Make sure the current user is an admin in the seeded workspace and that the API is running."
      />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Admin"
        title="Operational configuration"
        description="Adjust provider defaults, manage deterministic scoring versions, and review the latest audit events."
      />

      <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Provider defaults</CardTitle>
            <CardDescription>Workspace-specific SerpAPI defaults for language, geography, and enrichment breadth.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={providerForm.handleSubmit((values) => providerMutation.mutate(values))}>
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Language (`hl`)">
                  <Input {...providerForm.register("hl")} />
                </Field>
                <Field label="Geo (`gl`)">
                  <Input {...providerForm.register("gl")} />
                </Field>
                <Field label="Google domain">
                  <Input {...providerForm.register("google_domain")} />
                </Field>
                <Field label="Enrich top N">
                  <Input type="number" {...providerForm.register("enrich_top_n")} />
                </Field>
              </div>
              <Button type="submit" disabled={providerMutation.isPending}>
                {providerMutation.isPending ? "Saving..." : "Save provider settings"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Scoring configuration</CardTitle>
            <CardDescription>Create versioned scoring rules and activate the one the workspace should use.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {scoringQuery.data ? (
              <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">Active version</p>
                <p className="mt-2 text-lg font-bold">{scoringQuery.data.active_version.public_id}</p>
                <p className="mt-2 text-sm text-[color:var(--muted)]">
                  Created {formatDate(scoringQuery.data.active_version.created_at)} by{" "}
                  {scoringQuery.data.active_version.created_by_user_public_id}
                </p>
              </div>
            ) : null}

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
              <div className="grid gap-3 md:grid-cols-2">
                <Field label="local_trust">
                  <Input type="number" step="0.01" {...scoringForm.register("local_trust")} />
                </Field>
                <Field label="website_presence">
                  <Input type="number" step="0.01" {...scoringForm.register("website_presence")} />
                </Field>
                <Field label="search_visibility">
                  <Input type="number" step="0.01" {...scoringForm.register("search_visibility")} />
                </Field>
                <Field label="opportunity">
                  <Input type="number" step="0.01" {...scoringForm.register("opportunity")} />
                </Field>
                <Field label="data_confidence">
                  <Input type="number" step="0.01" {...scoringForm.register("data_confidence")} />
                </Field>
                <Field label="high_min">
                  <Input type="number" step="0.01" {...scoringForm.register("high_min")} />
                </Field>
                <Field label="medium_min">
                  <Input type="number" step="0.01" {...scoringForm.register("medium_min")} />
                </Field>
                <Field label="low_min">
                  <Input type="number" step="0.01" {...scoringForm.register("low_min")} />
                </Field>
                <Field label="confidence_min">
                  <Input type="number" step="0.01" {...scoringForm.register("confidence_min")} />
                </Field>
              </div>
              <Field label="Version note">
                <Textarea {...scoringForm.register("note")} />
              </Field>
              <Button type="submit" disabled={createVersionMutation.isPending}>
                {createVersionMutation.isPending ? "Creating..." : "Create scoring version"}
              </Button>
            </form>

            <div className="space-y-3">
              {(versionsQuery.data?.items ?? []).map((version) => (
                <div key={version.public_id} className="rounded-2xl border border-[color:var(--border)] p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold">{version.public_id}</p>
                      <p className="mt-1 text-sm text-[color:var(--muted)]">{version.note ?? "No note"}</p>
                    </div>
                    <Button
                      variant="secondary"
                      disabled={
                        activateMutation.isPending || scoringQuery.data?.active_version.public_id === version.public_id
                      }
                      onClick={() => activateMutation.mutate(version.public_id)}
                    >
                      {scoringQuery.data?.active_version.public_id === version.public_id ? "Active" : "Activate"}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Audit log</CardTitle>
          <CardDescription>Most recent admin and lead workflow events recorded by the API.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {(auditQuery.data?.items ?? []).length === 0 ? (
            <EmptyState
              title="No audit entries yet"
              description="Events such as job creation, lead status changes, exports, and scoring activation will be listed here."
            />
          ) : (
            auditQuery.data?.items.map((entry) => (
              <div key={entry.public_id} className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-semibold">{entry.event_name}</p>
                    <p className="mt-1 text-sm text-[color:var(--muted)]">{entry.details}</p>
                  </div>
                  <div className="text-right text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">
                    <p>{entry.actor_user_public_id ?? "system"}</p>
                    <p className="mt-1">{formatDate(entry.created_at)}</p>
                  </div>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-semibold">{label}</label>
      {children}
    </div>
  );
}
