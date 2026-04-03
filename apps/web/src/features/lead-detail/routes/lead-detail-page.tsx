import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Sparkles } from "lucide-react";
import { useParams } from "react-router-dom";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { generateLeadAnalysis, getLatestLeadAnalysis } from "@/features/ai-analysis/api";
import { LeadMap } from "@/features/leads/components/lead-map";
import {
  addLeadNote,
  assignLead,
  getLead,
  getLeadEvidence,
  getLeadScoreBreakdown,
  listLeadActivity,
  refreshLead,
  updateLeadStatus,
} from "@/features/leads/api";
import { generateLeadOutreach, getLatestOutreach, updateOutreachDraft } from "@/features/outreach/api";
import { listUsers } from "@/features/users/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { bandTone, formatDate, formatPercent, formatScore, statusTone, titleCaseLabel } from "@/lib/presenters";
import type { LeadStatus } from "@/types/api";

export function LeadDetailPage() {
  const { leadId = "" } = useParams();
  const queryClient = useQueryClient();
  const [statusDraft, setStatusDraft] = useState<LeadStatus>("new");
  const [statusNote, setStatusNote] = useState("");
  const [noteDraft, setNoteDraft] = useState("");
  const [outreachSubjectDraft, setOutreachSubjectDraft] = useState("");
  const [outreachMessageDraft, setOutreachMessageDraft] = useState("");

  const leadQuery = useQuery({
    queryKey: ["lead", leadId],
    queryFn: () => getLead(leadId),
    enabled: Boolean(leadId),
  });
  const evidenceQuery = useQuery({
    queryKey: ["lead", leadId, "evidence"],
    queryFn: () => getLeadEvidence(leadId),
    enabled: Boolean(leadId),
  });
  const breakdownQuery = useQuery({
    queryKey: ["lead", leadId, "breakdown"],
    queryFn: () => getLeadScoreBreakdown(leadId),
    enabled: Boolean(leadId),
  });
  const activityQuery = useQuery({
    queryKey: ["lead", leadId, "activity"],
    queryFn: () => listLeadActivity(leadId),
    enabled: Boolean(leadId),
  });
  const latestAnalysisQuery = useQuery({
    queryKey: ["lead", leadId, "analysis", "latest"],
    queryFn: () => getLatestLeadAnalysis(leadId),
    enabled: Boolean(leadId),
  });
  const latestOutreachQuery = useQuery({
    queryKey: ["lead", leadId, "outreach", "latest"],
    queryFn: () => getLatestOutreach(leadId),
    enabled: Boolean(leadId),
  });
  const usersQuery = useQuery({
    queryKey: ["users", "workspace"],
    queryFn: listUsers,
  });

  useDocumentTitle(leadQuery.data?.company_name ?? "Lead Detail");

  useEffect(() => {
    if (leadQuery.data) {
      setStatusDraft(leadQuery.data.status);
    }
  }, [leadQuery.data]);

  useEffect(() => {
    const message = latestOutreachQuery.data?.message;
    setOutreachSubjectDraft(message?.subject ?? "");
    setOutreachMessageDraft(message?.message ?? "");
  }, [latestOutreachQuery.data?.message]);

  const refreshQueries = () => {
    queryClient.invalidateQueries({ queryKey: ["lead", leadId] });
    queryClient.invalidateQueries({ queryKey: ["leads"] });
    queryClient.invalidateQueries({ queryKey: ["lead", leadId, "evidence"] });
    queryClient.invalidateQueries({ queryKey: ["lead", leadId, "breakdown"] });
    queryClient.invalidateQueries({ queryKey: ["lead", leadId, "activity"] });
    queryClient.invalidateQueries({ queryKey: ["lead", leadId, "analysis", "latest"] });
    queryClient.invalidateQueries({ queryKey: ["lead", leadId, "outreach", "latest"] });
  };

  const statusMutation = useMutation({
    mutationFn: (payload: { status: LeadStatus; note?: string }) =>
      updateLeadStatus(leadId, payload.status, payload.note),
    onSuccess: () => {
      refreshQueries();
      setStatusNote("");
    },
  });
  const assignMutation = useMutation({
    mutationFn: (assigneeId: string | null) => assignLead(leadId, assigneeId),
    onSuccess: refreshQueries,
  });
  const analysisMutation = useMutation({
    mutationFn: () => generateLeadAnalysis(leadId),
    onSuccess: refreshQueries,
  });
  const outreachMutation = useMutation({
    mutationFn: () => generateLeadOutreach(leadId),
    onSuccess: refreshQueries,
  });
  const refreshMutation = useMutation({
    mutationFn: () => refreshLead(leadId),
    onSuccess: refreshQueries,
  });
  const noteMutation = useMutation({
    mutationFn: (note: string) => addLeadNote(leadId, note),
    onSuccess: () => {
      refreshQueries();
      setNoteDraft("");
    },
  });
  const saveOutreachMutation = useMutation({
    mutationFn: (messageId: string) =>
      updateOutreachDraft(messageId, {
        subject: outreachSubjectDraft.trim(),
        message: outreachMessageDraft.trim(),
      }),
    onSuccess: refreshQueries,
  });

  if (leadQuery.isError) {
    return (
      <EmptyState
        title="Lead detail is unavailable"
        description="The lead could not be loaded for the current workspace or session."
      />
    );
  }

  if (!leadQuery.data) {
    return <p className="text-sm text-[color:var(--muted)]">Loading lead details...</p>;
  }

  const lead = leadQuery.data;
  const latestAnalysis = latestAnalysisQuery.data?.snapshot ?? null;
  const latestOutreach = latestOutreachQuery.data?.message ?? null;
  const outreachDraftChanged =
    latestOutreach !== null &&
    (outreachSubjectDraft !== latestOutreach.subject ||
      outreachMessageDraft !== latestOutreach.message);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Lead detail"
        title={lead.company_name}
        description="Review the current operational lead record, inspect normalized evidence, and generate assistive analysis and outreach from stored facts."
        action={
          <div className="flex flex-wrap items-center gap-3">
            <Badge tone={bandTone(lead.latest_band)}>{formatScore(lead.latest_score)}</Badge>
            <Button variant="secondary" onClick={() => refreshMutation.mutate()} disabled={refreshMutation.isPending}>
              <RefreshCw className="me-2 h-4 w-4" />
              {refreshMutation.isPending ? "Refreshing..." : "Refresh lead"}
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <Card>
          <CardHeader>
            <CardTitle>Stored facts</CardTitle>
            <CardDescription>The live record reflects the latest operational view assembled from normalized provider facts.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Badge tone={bandTone(lead.latest_band)}>
                {lead.latest_band ? titleCaseLabel(lead.latest_band) : "Unscored"}
              </Badge>
              <Badge tone={statusTone(lead.status)}>{titleCaseLabel(lead.status)}</Badge>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <FactCard label="City" value={lead.city ?? "Unknown"} />
              <FactCard label="Website" value={lead.website_url ?? "Missing"} />
              <FactCard label="Reviews" value={String(lead.review_count)} />
              <FactCard label="Rating" value={lead.rating ? String(lead.rating) : "N/A"} />
              <FactCard label="Completeness" value={formatPercent(lead.data_completeness)} />
              <FactCard label="Confidence" value={formatPercent(lead.data_confidence)} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Location and workflow</CardTitle>
            <CardDescription>Map state and lead operations are coordinated here.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="h-[280px] overflow-hidden rounded-2xl border border-[color:var(--border)]">
              {lead.lat !== null && lead.lng !== null ? (
                <LeadMap className="h-full" leads={[lead]} selectedLeadId={lead.public_id} />
              ) : (
                <div className="flex h-full items-center justify-center bg-[color:var(--surface-soft)] text-sm text-[color:var(--muted)]">
                  No coordinate evidence is stored for this lead yet.
                </div>
              )}
            </div>
            <div className="space-y-2">
              <label className="text-sm font-semibold">Assignee</label>
              <Select
                data-testid="lead-detail-assignee-select"
                value={lead.assigned_to_user_public_id ?? ""}
                onChange={(event) => assignMutation.mutate(event.target.value || null)}
              >
                <option value="">Unassigned</option>
                {(usersQuery.data?.items ?? []).map((user) => (
                  <option key={user.public_id} value={user.public_id}>
                    {user.full_name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-semibold">Next status</label>
              <Select
                data-testid="lead-detail-status-select"
                value={statusDraft}
                onChange={(event) => setStatusDraft(event.target.value as LeadStatus)}
              >
                <option value="new">New</option>
                <option value="reviewed">Reviewed</option>
                <option value="qualified">Qualified</option>
                <option value="contacted">Contacted</option>
                <option value="interested">Interested</option>
                <option value="won">Won</option>
                <option value="lost">Lost</option>
                <option value="archived">Archived</option>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-semibold">Status note</label>
              <Textarea
                value={statusNote}
                onChange={(event) => setStatusNote(event.target.value)}
                placeholder="Optional note to store with this status change"
              />
            </div>
            <Button className="w-full justify-center" onClick={() => statusMutation.mutate({ status: statusDraft, note: statusNote || undefined })}>
              Save status update
            </Button>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
        <Card>
          <CardHeader>
            <CardTitle>Latest score breakdown</CardTitle>
            <CardDescription>Deterministic score output and contribution-level explanations.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {breakdownQuery.data ? (
              <div className="space-y-3 text-sm leading-6">
                <div className="rounded-2xl border border-[color:var(--border)] p-4">
                  <p className="font-semibold">Version</p>
                  <p className="mt-2 text-[color:var(--muted)]">{breakdownQuery.data.scoring_version_id}</p>
                </div>
                {breakdownQuery.data.breakdown.map((item) => (
                  <div key={item.key} className="rounded-2xl border border-[color:var(--border)] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-semibold">{item.label}</p>
                      <Badge tone="neutral">{item.contribution.toFixed(1)}</Badge>
                    </div>
                    <p className="mt-2 text-[color:var(--muted)]">{item.reason}</p>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No score breakdown"
                description="Once deterministic scoring runs against normalized facts, its persisted breakdown will be shown here."
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Normalized evidence</CardTitle>
            <CardDescription>Evidence rows include fetch metadata, confidence, completeness, and the normalized fact payload.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {evidenceQuery.data?.items.length ? (
              <div className="space-y-3">
                {evidenceQuery.data.items.map((item) => (
                  <div
                    key={`${item.provider_fetch_public_id}-${item.created_at}`}
                    className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4 text-sm text-[color:var(--muted)]"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-[color:var(--text)]">{titleCaseLabel(item.source_type)}</p>
                        <p className="mt-1 text-xs uppercase tracking-[0.16em]">
                          {item.request_mode} / {item.provider_status} / {item.provider_fetch_public_id}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Badge tone="accent">Confidence {Math.round(item.confidence * 100)}%</Badge>
                        <Badge tone="neutral">Completeness {Math.round(item.completeness * 100)}%</Badge>
                      </div>
                    </div>
                    <p className="mt-3">{item.address ?? item.city ?? "No address captured"}</p>
                    <pre className="mt-3 overflow-x-auto rounded-xl border border-[color:var(--border)] bg-white/80 p-3 text-xs leading-6 text-slate-700">
                      {JSON.stringify(item.facts, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No evidence rows"
                description="No normalized evidence has been stored for this lead yet."
              />
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Lead activity</CardTitle>
          <CardDescription>Track status changes and internal notes for this lead in one operational timeline.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 xl:grid-cols-[0.42fr_0.58fr]">
          <div className="space-y-3">
            <label className="text-sm font-semibold">Add note</label>
            <Textarea
              value={noteDraft}
              onChange={(event) => setNoteDraft(event.target.value)}
              placeholder="Capture a qualification note, call outcome, or next-step context"
            />
            <Button
              className="w-full justify-center"
              onClick={() => noteMutation.mutate(noteDraft.trim())}
              disabled={noteMutation.isPending || noteDraft.trim().length === 0}
            >
              {noteMutation.isPending ? "Saving..." : "Save note"}
            </Button>
          </div>
          <div className="space-y-3">
            {activityQuery.data?.items.length ? (
              activityQuery.data.items.map((item) => (
                <div key={item.entry_id} className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold">
                        {item.entry_type === "status_change" ? "Status updated" : "Internal note"}
                      </p>
                      <p className="mt-1 text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">
                        {(item.actor_full_name ?? "Unknown user")} / {formatDate(item.created_at)}
                      </p>
                    </div>
                    <Badge tone={item.entry_type === "status_change" ? "accent" : "neutral"}>
                      {item.entry_type === "status_change" ? "Status" : "Note"}
                    </Badge>
                  </div>
                  {item.entry_type === "status_change" ? (
                    <p className="mt-3 text-sm leading-6 text-[color:var(--muted)]">
                      {item.from_status ? titleCaseLabel(item.from_status) : "Initial"} to{" "}
                      {item.to_status ? titleCaseLabel(item.to_status) : "Unknown"}
                    </p>
                  ) : (
                    <p className="mt-3 whitespace-pre-line text-sm leading-6 text-[color:var(--muted)]">{item.note}</p>
                  )}
                </div>
              ))
            ) : (
              <EmptyState
                title="No activity yet"
                description="Status updates and manual notes will accumulate here as the lead moves through the workflow."
              />
            )}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Assistive analysis</CardTitle>
            <CardDescription>Generated from stored facts and persisted separately from lead truth data.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button variant="secondary" onClick={() => analysisMutation.mutate()} disabled={analysisMutation.isPending}>
              <Sparkles className="me-2 h-4 w-4" />
              {analysisMutation.isPending ? "Generating..." : "Generate analysis"}
            </Button>
            {latestAnalysis ? (
              <div className="space-y-4 rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
                <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">
                  <span>{latestAnalysis.ai_provider}</span>
                  <span>{latestAnalysis.model_name}</span>
                  <span>{formatDate(latestAnalysis.created_at)}</span>
                </div>
                <p className="text-sm leading-6 text-[color:var(--muted)]">{latestAnalysis.analysis.summary}</p>
                <div>
                  <p className="font-semibold">Weaknesses</p>
                  <ul className="mt-2 space-y-2 text-sm text-[color:var(--muted)]">
                    {latestAnalysis.analysis.weaknesses.map((item) => (
                      <li key={item}>- {item}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="font-semibold">Opportunities</p>
                  <ul className="mt-2 space-y-2 text-sm text-[color:var(--muted)]">
                    {latestAnalysis.analysis.opportunities.map((item) => (
                      <li key={item}>- {item}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="font-semibold">Recommended services</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {latestAnalysis.service_recommendations.map((item) => (
                      <Badge key={item.public_id} tone="accent">
                        {item.service_name}
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-sm text-[color:var(--muted)]">
                Run the assistive analysis to generate a fact-based summary.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Outreach draft</CardTitle>
            <CardDescription>Subject and message draft produced from the same stored facts and score context.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button variant="secondary" onClick={() => outreachMutation.mutate()} disabled={outreachMutation.isPending}>
              {outreachMutation.isPending ? "Drafting..." : "Generate outreach draft"}
            </Button>
            {latestOutreach ? (
              <div className="space-y-3 rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
                <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">
                  <span>{formatDate(latestOutreach.updated_at)}</span>
                  <span>{latestOutreach.has_manual_edits ? "Edited draft" : "Generated draft"}</span>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold">Subject</label>
                  <Input
                    data-testid="lead-detail-outreach-subject"
                    value={outreachSubjectDraft}
                    onChange={(event) => setOutreachSubjectDraft(event.target.value)}
                    placeholder="Draft subject"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold">Message</label>
                  <Textarea
                    data-testid="lead-detail-outreach-message"
                    value={outreachMessageDraft}
                    onChange={(event) => setOutreachMessageDraft(event.target.value)}
                    className="min-h-[220px]"
                    placeholder="Draft outreach message"
                  />
                </div>
                <div className="flex flex-wrap gap-3">
                  <Button
                    onClick={() => saveOutreachMutation.mutate(latestOutreach.public_id)}
                    disabled={
                      saveOutreachMutation.isPending ||
                      outreachSubjectDraft.trim().length === 0 ||
                      outreachMessageDraft.trim().length === 0 ||
                      !outreachDraftChanged
                    }
                  >
                    {saveOutreachMutation.isPending ? "Saving..." : "Save edits"}
                  </Button>
                  {latestOutreach.has_manual_edits ? (
                    <Badge tone="neutral">Generated copy retained below</Badge>
                  ) : null}
                </div>
                {latestOutreach.has_manual_edits ? (
                  <div className="space-y-2 rounded-xl border border-[color:var(--border)] bg-white/70 p-3">
                    <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">Original generated draft</p>
                    <p className="font-semibold">{latestOutreach.generated_subject}</p>
                    <p className="whitespace-pre-line text-sm leading-6 text-[color:var(--muted)]">
                      {latestOutreach.generated_message}
                    </p>
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="text-sm text-[color:var(--muted)]">
                Generate a draft when the lead is ready for outbound messaging.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function FactCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[color:var(--border)] p-4">
      <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">{label}</p>
      <p className="mt-2 font-semibold">{value}</p>
    </div>
  );
}
