import { useMemo, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { RotateCcw, Sparkles, Square } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useAuthSession } from "@/features/auth/session";
import { getLeadEvidenceGraph } from "@/features/leads/research-api";
import { safeHttpUrl } from "@/lib/safe-url";

import { isBusy, parseFinalAnswer, pendingActions, type CopilotPhase } from "../agent-state";
import { useAgentRun } from "../use-agent-run";
import { ActionCard } from "./action-card";
import { ActivityList } from "./activity-list";
import { FinalAnswerView, type EvidenceLabel } from "./final-answer";

const SUGGESTION_KEYS = ["summarize", "outreach", "nextStep", "fit"] as const;
const GOAL_MAX_LENGTH = 2000;

const PHASE_KEY: Record<CopilotPhase, string> = {
  idle: "copilot.phase.idle",
  starting: "copilot.phase.starting",
  running: "copilot.phase.running",
  waiting_for_approval: "copilot.phase.waiting",
  resuming: "copilot.phase.resuming",
  completed: "copilot.phase.completed",
  failed: "copilot.phase.failed",
  cancelled: "copilot.phase.cancelled",
  expired: "copilot.phase.expired",
};

interface CopilotPanelProps {
  leadId: string;
  leadName: string;
}

export function CopilotPanel({ leadId, leadName }: CopilotPanelProps) {
  const { t } = useTranslation();
  const { user } = useAuthSession();
  const { state, start, cancel, approve, reject, reset } = useAgentRun();
  const [goal, setGoal] = useState("");

  // Mirrors the server gate (`leads:manage`); the server remains the authority.
  const canDecide = user?.permissions.includes("leads:manage") ?? false;
  const busy = isBusy(state.phase);
  const graphQuery = useQuery({
    queryKey: ["lead", leadId, "evidence-graph"],
    queryFn: () => getLeadEvidenceGraph(leadId),
    // Only needed to label the citations in a finished answer.
    enabled: state.phase === "completed",
  });

  const evidenceIndex = useMemo(() => {
    const index = new Map<string, EvidenceLabel>();
    for (const group of graphQuery.data?.groups ?? []) {
      for (const fact of group.facts) {
        for (const source of fact.sources) {
          if (source.evidence_ref && !index.has(source.evidence_ref)) {
            index.set(source.evidence_ref, {
              label: `${fact.claim_type}: ${fact.value}`,
              url: safeHttpUrl(source.url),
            });
          }
        }
      }
    }
    return index;
  }, [graphQuery.data]);

  const answer = useMemo(() => parseFinalAnswer(state.run?.final_answer ?? null), [state.run]);
  const pending = pendingActions(state);
  const allActions = state.actionOrder.map((id) => state.actions[id]);
  const decidedActions = allActions.filter((action) => action.status !== "pending");
  const deciding = Object.keys(state.decisions).length > 0;
  const showLoadingSkeleton = state.phase === "starting" && state.activity.length === 0;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = goal.trim();
    if (!trimmed || busy) return;
    void start({ goal: trimmed, leadId, profile: "sales_copilot" });
  }

  function ask(question: string) {
    setGoal(question);
    void start({ goal: question, leadId, profile: "sales_copilot" });
  }

  return (
    <Card role="region" aria-labelledby="copilot-title" className="overflow-hidden rounded-[1.5rem] border-border bg-card/95">
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle id="copilot-title" role="heading" aria-level={2} className="flex items-center gap-2">
            <Sparkles className="size-4" aria-hidden />
            {t("copilot.title")}
          </CardTitle>
          {state.phase !== "idle" ? (
            <Badge tone={phaseTone(state.phase)} aria-live="polite">
              {t(PHASE_KEY[state.phase])}
            </Badge>
          ) : null}
        </div>
        <CardDescription>{t("copilot.description", { lead: leadName })}</CardDescription>
      </CardHeader>

      <CardContent className="space-y-5">
        <form onSubmit={submit} className="space-y-3">
          <label htmlFor="copilot-goal" className="sr-only">
            {t("copilot.goalLabel")}
          </label>
          <Textarea
            id="copilot-goal"
            value={goal}
            rows={2}
            maxLength={GOAL_MAX_LENGTH}
            disabled={busy}
            placeholder={t("copilot.goalPlaceholder")}
            onChange={(event) => setGoal(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) event.currentTarget.form?.requestSubmit();
            }}
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" size="sm" disabled={busy || goal.trim() === ""}>
              {busy ? t("copilot.working") : t("copilot.ask")}
            </Button>
            {busy && state.runId ? (
              <Button type="button" size="sm" variant="outline" className="bg-transparent" onClick={() => void cancel()}>
                <Square className="size-3" aria-hidden />
                {t("copilot.cancel")}
              </Button>
            ) : null}
            {state.phase !== "idle" && !busy ? (
              <Button type="button" size="sm" variant="ghost" onClick={reset}>
                <RotateCcw className="size-3.5" aria-hidden />
                {t("copilot.newQuestion")}
              </Button>
            ) : null}
          </div>
          {state.phase === "idle" ? (
            <div className="flex flex-wrap gap-2" role="list" aria-label={t("copilot.suggestionsLabel")}>
              {SUGGESTION_KEYS.map((key) => (
                <Button
                  key={key}
                  type="button"
                  size="sm"
                  variant="outline"
                  role="listitem"
                  className="h-auto whitespace-normal bg-transparent py-1.5 text-start"
                  onClick={() => ask(t(`copilot.suggestions.${key}`))}
                >
                  {t(`copilot.suggestions.${key}`)}
                </Button>
              ))}
            </div>
          ) : null}
        </form>

        {state.phase === "idle" ? <p className="text-xs text-muted-foreground">{t("copilot.emptyHint")}</p> : null}

        {showLoadingSkeleton ? (
          <div className="space-y-2" aria-busy="true" aria-label={t("copilot.phase.starting")}>
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        ) : null}

        <ActivityList items={state.activity} live={busy} />

        {state.connection === "reconnecting" ? (
          <p role="status" className="text-xs text-muted-foreground">
            {t("copilot.connection.reconnecting")}
          </p>
        ) : null}
        {state.connection === "failed" && !isDone(state.phase) ? (
          <p role="status" className="text-xs text-[oklch(var(--caution))]">
            {t("copilot.connection.failed")}
          </p>
        ) : null}

        {state.budgetExhausted ? (
          <p role="status" className="rounded-lg border border-[oklch(var(--caution)/0.3)] bg-[oklch(var(--caution)/0.08)] p-2.5 text-xs">
            {t("copilot.budgetReached")}
          </p>
        ) : null}

        {pending.length > 0 ? (
          <section aria-label={t("copilot.approvals.title")} className="space-y-3">
            <div>
              <h3 className="text-sm font-semibold">{t("copilot.approvals.title")}</h3>
              <p className="text-xs text-muted-foreground">{t("copilot.approvals.description")}</p>
            </div>
            {pending.map((action, index) => (
              <ActionCard
                key={action.action_id}
                action={action}
                queuePosition={index + 1}
                queueTotal={pending.length}
                deciding={state.decisions[action.action_id] ?? null}
                locked={deciding}
                canDecide={canDecide}
                onApprove={(id) => void approve(id)}
                onReject={(id, reason) => void reject(id, reason)}
              />
            ))}
          </section>
        ) : null}

        {state.phase === "resuming" ? (
          <p role="status" className="text-xs text-muted-foreground">
            {t("copilot.approvals.resuming")}
          </p>
        ) : null}

        {state.errorKey ? (
          <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-2.5 text-sm">
            {t(state.errorKey)}
          </p>
        ) : null}

        {state.phase === "failed" && !state.errorKey ? (
          <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-2.5 text-sm">
            {t("copilot.errors.runFailed")}
          </p>
        ) : null}

        {answer && state.phase === "completed" ? (
          <FinalAnswerView
            answer={answer}
            knowledge={state.knowledge}
            evidenceIndex={evidenceIndex}
            actions={decidedActions}
            onAsk={ask}
            asking={busy}
          />
        ) : null}

        {state.phase === "completed" && !answer ? (
          <p className="text-sm text-muted-foreground">{t("copilot.answer.unavailable")}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function isDone(phase: CopilotPhase): boolean {
  return phase === "completed" || phase === "failed" || phase === "cancelled" || phase === "expired";
}

function phaseTone(phase: CopilotPhase): "info" | "warning" | "success" | "danger" | "neutral" {
  switch (phase) {
    case "waiting_for_approval":
      return "warning";
    case "completed":
      return "success";
    case "failed":
      return "danger";
    case "cancelled":
    case "expired":
      return "neutral";
    default:
      return "info";
  }
}
