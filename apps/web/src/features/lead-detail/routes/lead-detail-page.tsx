import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { LeadActivityPanel } from "@/components/lead/activity-panel";
import { LeadAiAnalysisPanel } from "@/components/lead/ai-analysis-panel";
import { LeadEvidenceTimeline } from "@/components/lead/evidence-timeline";
import { LeadHero } from "@/components/lead/lead-hero";
import { LeadOutreachPanel } from "@/components/lead/outreach-panel";
import { LeadScoreBreakdownCard } from "@/components/lead/score-breakdown";
import { EmptyState } from "@/components/shared/empty-state";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { generateLeadAnalysis, getLatestLeadAnalysis } from "@/features/ai-analysis/api";
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
import { buildBreakdownSummary, buildEvidenceSummary, buildLeadHealth, mergeActivityTimeline } from "@/features/internal/design-adapters";
import { generateLeadOutreach, getLatestOutreach, updateOutreachDraft } from "@/features/outreach/api";
import { listUsers } from "@/features/users/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { hasCoordinates } from "@/lib/maps";
import { formatPercent, formatScore, titleCaseLabel } from "@/lib/presenters";
import { LazyLeadMap } from "@/features/leads/components/lazy-lead-map";
import type { LeadStatus, OutreachTone } from "@/types/api";

export function LeadDetailPage() {
  const { leadId = "" } = useParams();
  const queryClient = useQueryClient();
  const [statusDraft, setStatusDraft] = useState<LeadStatus>("new");
  const [statusNote, setStatusNote] = useState("");
  const [noteDraft, setNoteDraft] = useState("");
  const [outreachSubjectDraft, setOutreachSubjectDraft] = useState("");
  const [outreachMessageDraft, setOutreachMessageDraft] = useState("");
  const [outreachTone, setOutreachTone] = useState<OutreachTone>("consultative");
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

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
    setOutreachTone(message?.tone ?? "consultative");
  }, [latestOutreachQuery.data?.message]);

  const refreshQueries = () => {
    void queryClient.invalidateQueries({ queryKey: ["lead", leadId] });
    void queryClient.invalidateQueries({ queryKey: ["leads"] });
    void queryClient.invalidateQueries({ queryKey: ["lead", leadId, "evidence"] });
    void queryClient.invalidateQueries({ queryKey: ["lead", leadId, "breakdown"] });
    void queryClient.invalidateQueries({ queryKey: ["lead", leadId, "activity"] });
    void queryClient.invalidateQueries({ queryKey: ["lead", leadId, "analysis", "latest"] });
    void queryClient.invalidateQueries({ queryKey: ["lead", leadId, "outreach", "latest"] });
  };

  const statusMutation = useMutation({
    mutationFn: (payload: { status: LeadStatus; note?: string }) => updateLeadStatus(leadId, payload.status, payload.note),
    onSuccess: () => {
      refreshQueries();
      setStatusNote("");
      setActionSuccess("Lead status updated.");
    },
  });
  const assignMutation = useMutation({
    mutationFn: (assigneeId: string | null) => assignLead(leadId, assigneeId),
    onSuccess: (_payload, assigneeId) => {
      refreshQueries();
      setActionSuccess(assigneeId ? "Lead owner updated." : "Lead owner cleared.");
    },
  });
  const analysisMutation = useMutation({
    mutationFn: () => generateLeadAnalysis(leadId),
    onSuccess: () => {
      refreshQueries();
      setActionSuccess("Assistive analysis generated.");
    },
  });
  const outreachMutation = useMutation({
    mutationFn: (regenerate: boolean) => generateLeadOutreach(leadId, { tone: outreachTone, regenerate }),
    onSuccess: () => {
      refreshQueries();
      setActionSuccess("Outreach draft generated.");
    },
  });
  const refreshMutation = useMutation({
    mutationFn: () => refreshLead(leadId),
    onSuccess: () => {
      refreshQueries();
      setActionSuccess("Lead refresh completed.");
    },
  });
  const noteMutation = useMutation({
    mutationFn: (note: string) => addLeadNote(leadId, note),
    onSuccess: () => {
      refreshQueries();
      setNoteDraft("");
      setActionSuccess("Note saved.");
    },
  });
  const saveOutreachMutation = useMutation({
    mutationFn: (messageId: string) =>
      updateOutreachDraft(messageId, {
        subject: outreachSubjectDraft.trim(),
        message: outreachMessageDraft.trim(),
      }),
    onSuccess: () => {
      refreshQueries();
      setActionSuccess("Outreach draft saved.");
    },
  });

  if (leadQuery.isError) {
    return <EmptyState title="Lead detail is unavailable" description={leadQuery.error.message} />;
  }

  if (leadQuery.isPending || !leadQuery.data) {
    return (
      <QueryStateNotice
        tone="loading"
        title="Loading lead detail"
        description="Fetching the live lead record, evidence, activity, and latest assistive outputs."
      />
    );
  }

  const lead = leadQuery.data;
  const breakdown = breakdownQuery.data ?? null;
  const evidenceItems = evidenceQuery.data?.items ?? [];
  const latestAnalysis = latestAnalysisQuery.data?.snapshot ?? null;
  const latestOutreach = latestOutreachQuery.data?.message ?? null;
  const outreachDraftChanged =
    latestOutreach !== null &&
    (outreachSubjectDraft !== latestOutreach.subject || outreachMessageDraft !== latestOutreach.message);
  const healthSignals = buildLeadHealth(lead);
  const evidenceSummary = buildEvidenceSummary(evidenceItems);
  const breakdownSummary = buildBreakdownSummary(breakdown);
  const activityItems = mergeActivityTimeline(activityQuery.data?.items ?? []);

  return (
    <div className="space-y-6 p-3 sm:p-4 lg:p-6">
      <LeadHero
        lead={lead}
        onRefresh={() => refreshMutation.mutate()}
        refreshing={refreshMutation.isPending}
        onGenerateAnalysis={() => analysisMutation.mutate()}
        generatingAnalysis={analysisMutation.isPending}
      />

      {actionSuccess ? <QueryStateNotice tone="success" title="Action completed" description={actionSuccess} /> : null}

      <section className="grid gap-4 2xl:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-4">
          <Card className="rounded-[1.5rem] border-border bg-card/95">
            <CardHeader>
              <CardTitle>Normalized facts and workflow</CardTitle>
              <CardDescription>
                Imported fact tiles are now fed by the current canonical lead record from the API.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              <FactCard label="Lead score" value={formatScore(lead.latest_score)} />
              <FactCard label="Band" value={lead.latest_band ? titleCaseLabel(lead.latest_band) : "Unscored"} />
              <FactCard label="Reviews" value={String(lead.review_count)} />
              <FactCard label="Rating" value={lead.rating ? String(lead.rating) : "N/A"} />
              <FactCard label="Confidence" value={formatPercent(lead.data_confidence)} />
              <FactCard label="Completeness" value={formatPercent(lead.data_completeness)} />
              <FactCard label="Qualified" value={lead.latest_qualified ? "Yes" : "No"} />
              <FactCard label="Website" value={lead.website_domain ?? "Missing"} />
            </CardContent>
          </Card>

          <LeadScoreBreakdownCard
            totalScore={breakdown?.total_score ?? lead.latest_score ?? 0}
            qualified={breakdown?.qualified ?? Boolean(lead.latest_qualified)}
            scoringVersionId={breakdown?.scoring_version_id}
            items={breakdownSummary}
          />

          {evidenceQuery.isPending ? (
            <QueryStateNotice tone="loading" title="Loading evidence" description="Fetching normalized provider facts for this lead." />
          ) : evidenceQuery.isError ? (
            <QueryStateNotice tone="error" title="Evidence rows are unavailable" description={evidenceQuery.error.message} />
          ) : evidenceItems.length > 0 ? (
            <LeadEvidenceTimeline items={evidenceItems} summary={evidenceSummary} />
          ) : (
            <QueryStateNotice
              tone="info"
              title="No evidence rows"
              description="No normalized evidence has been stored for this lead yet."
            />
          )}
        </div>

        <div className="space-y-4">
          <Card className="rounded-[1.5rem] border-border bg-card/95">
            <CardHeader>
              <CardTitle>Lead operations</CardTitle>
              <CardDescription>Assignment, status control, map context, and evidence health remain in one panel.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {healthSignals.map((item) => (
                  <div key={item.label} className="rounded-xl border border-border bg-muted/20 p-4">
                    <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{item.label}</p>
                    <p className="mt-2 text-xl font-semibold">{item.value}%</p>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.helper}</p>
                  </div>
                ))}
              </div>

              <div className="h-[260px] overflow-hidden rounded-2xl border border-border">
                {hasCoordinates(lead) ? (
                  <LazyLeadMap className="h-full" leads={[lead]} selectedLeadId={lead.public_id} />
                ) : (
                  <EmptyState
                    className="h-full border-0"
                    title="No map location yet"
                    description="Coordinate evidence has not been stored for this lead yet."
                  />
                )}
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-2">
                  <Label>Assignee</Label>
                  <Select
                    value={lead.assigned_to_user_public_id ?? "unassigned"}
                    disabled={assignMutation.isPending}
                    onValueChange={(value) => assignMutation.mutate(value === "unassigned" ? null : value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Unassigned" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="unassigned">Unassigned</SelectItem>
                      {(usersQuery.data?.items ?? []).map((user) => (
                        <SelectItem key={user.public_id} value={user.public_id}>
                          {user.full_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Next status</Label>
                  <Select value={statusDraft} onValueChange={(value) => setStatusDraft(value as LeadStatus)}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select status" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="new">New</SelectItem>
                      <SelectItem value="reviewed">Reviewed</SelectItem>
                      <SelectItem value="qualified">Qualified</SelectItem>
                      <SelectItem value="contacted">Contacted</SelectItem>
                      <SelectItem value="interested">Interested</SelectItem>
                      <SelectItem value="won">Won</SelectItem>
                      <SelectItem value="lost">Lost</SelectItem>
                      <SelectItem value="archived">Archived</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label>Status note</Label>
                <Textarea
                  value={statusNote}
                  onChange={(event) => setStatusNote(event.target.value)}
                  placeholder="Optional note to store with this status change"
                />
              </div>

              <Button onClick={() => statusMutation.mutate({ status: statusDraft, note: statusNote || undefined })} disabled={statusMutation.isPending}>
                {statusMutation.isPending ? "Saving..." : "Save status update"}
              </Button>
            </CardContent>
          </Card>

          <LeadAiAnalysisPanel
            snapshot={latestAnalysis}
            onGenerate={() => analysisMutation.mutate()}
            generating={analysisMutation.isPending}
            error={latestAnalysisQuery.isError ? latestAnalysisQuery.error.message : null}
          />

          <LeadOutreachPanel
            draft={latestOutreach}
            tone={outreachTone}
            onToneChange={setOutreachTone}
            subject={outreachSubjectDraft}
            message={outreachMessageDraft}
            onSubjectChange={setOutreachSubjectDraft}
            onMessageChange={setOutreachMessageDraft}
            onGenerate={(regenerate) => outreachMutation.mutate(regenerate)}
            onSave={() => latestOutreach && saveOutreachMutation.mutate(latestOutreach.public_id)}
            generating={outreachMutation.isPending}
            saving={saveOutreachMutation.isPending}
            canSave={
              latestOutreach !== null &&
              outreachSubjectDraft.trim().length > 0 &&
              outreachMessageDraft.trim().length > 0 &&
              outreachDraftChanged
            }
            error={latestOutreachQuery.isError ? latestOutreachQuery.error.message : null}
          />
        </div>
      </section>

      <LeadActivityPanel
        items={activityItems}
        noteDraft={noteDraft}
        onNoteChange={setNoteDraft}
        onSaveNote={() => noteMutation.mutate(noteDraft.trim())}
        saving={noteMutation.isPending}
        error={noteMutation.isError ? noteMutation.error.message : null}
      />
    </div>
  );
}

function FactCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-muted/20 p-4">
      <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="mt-2 font-semibold">{value}</p>
    </div>
  );
}
