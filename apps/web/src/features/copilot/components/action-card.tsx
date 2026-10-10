import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Check, ShieldAlert, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { AgentAction } from "@/types/agent";

import { actionStatusPresentation, buildActionView, isSendTool } from "../action-preview";

interface ActionCardProps {
  action: AgentAction;
  /** 1-based position among this run's pending actions, or null once decided. */
  queuePosition: number | null;
  queueTotal: number;
  /** A decision for this action is in flight. */
  deciding: "approve" | "reject" | null;
  /** Another action's decision is in flight; approvals are strictly sequential. */
  locked: boolean;
  canDecide: boolean;
  onApprove: (actionId: string) => void;
  onReject: (actionId: string, reason?: string) => void;
}

export function ActionCard({
  action,
  queuePosition,
  queueTotal,
  deciding,
  locked,
  canDecide,
  onApprove,
  onReject,
}: ActionCardProps) {
  const { t } = useTranslation();
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const view = buildActionView(action);
  const status = actionStatusPresentation(action.status);
  const pending = action.status === "pending";
  const busy = deciding !== null;
  const headingId = `action-${action.action_id}-title`;

  return (
    <article
      aria-labelledby={headingId}
      className="rounded-2xl border border-border bg-card p-4 shadow-sm"
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h4 id={headingId} className="text-sm font-semibold">
            {t(view.titleKey)}
          </h4>
          {pending && queueTotal > 1 && queuePosition !== null ? (
            <p className="mt-0.5 text-xs text-muted-foreground">
              {t("copilot.actions.queue", { position: queuePosition, total: queueTotal })}
            </p>
          ) : null}
        </div>
        <Badge tone={status.tone}>{t(status.labelKey)}</Badge>
      </header>

      {view.irreversible ? (
        <p className="mt-3 flex items-start gap-2 rounded-lg border border-[oklch(var(--caution)/0.3)] bg-[oklch(var(--caution)/0.08)] p-2.5 text-xs">
          <ShieldAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>{t("copilot.actions.irreversible")}</span>
        </p>
      ) : null}

      {view.draft ? (
        <div className="mt-3 space-y-3">
          {view.draft.current ? (
            <DraftBlock label={t("copilot.preview.current")} draft={view.draft.current} muted />
          ) : null}
          <DraftBlock label={t("copilot.preview.proposed")} draft={view.draft.proposed} />
        </div>
      ) : (
        <dl className="mt-3 space-y-2 text-sm">
          {view.rows.map((row) => (
            <div key={row.labelKey} className={row.block ? "space-y-1" : "flex flex-wrap gap-x-2"}>
              <dt className="text-muted-foreground">{t(row.labelKey, { defaultValue: "" })}</dt>
              <dd className={row.block ? "whitespace-pre-line rounded-lg bg-muted/30 p-2.5" : "font-medium"}>
                {row.value}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {isSendTool(action.tool_name) ? (
        <p className="mt-3 text-xs text-muted-foreground">{t("copilot.actions.sendDisabled")}</p>
      ) : null}

      {action.status === "failed" ? (
        <p role="alert" className="mt-3 text-xs text-destructive">
          {t("copilot.actions.failedNote")}
        </p>
      ) : null}

      {pending ? (
        canDecide ? (
          <div className="mt-4 space-y-2">
            {rejecting ? (
              <div className="space-y-2">
                <label className="text-xs text-muted-foreground" htmlFor={`${headingId}-reason`}>
                  {t("copilot.actions.rejectReason")}
                </label>
                <Textarea
                  id={`${headingId}-reason`}
                  value={reason}
                  maxLength={500}
                  rows={2}
                  onChange={(event) => setReason(event.target.value)}
                />
              </div>
            ) : null}
            <div className="flex flex-wrap gap-2">
              {rejecting ? (
                <>
                  <Button
                    size="sm"
                    variant="destructive"
                    disabled={busy || locked}
                    onClick={() => onReject(action.action_id, reason.trim() || undefined)}
                  >
                    <X className="size-3.5" aria-hidden />
                    {deciding === "reject" ? t("copilot.actions.rejecting") : t("copilot.actions.confirmReject")}
                  </Button>
                  <Button size="sm" variant="ghost" disabled={busy} onClick={() => setRejecting(false)}>
                    {t("common.cancel")}
                  </Button>
                </>
              ) : (
                <>
                  <Button size="sm" disabled={busy || locked} onClick={() => onApprove(action.action_id)}>
                    <Check className="size-3.5" aria-hidden />
                    {deciding === "approve" ? t("copilot.actions.approving") : t("copilot.actions.approve")}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="bg-transparent"
                    disabled={busy || locked}
                    onClick={() => setRejecting(true)}
                  >
                    {t("copilot.actions.reject")}
                  </Button>
                </>
              )}
            </div>
          </div>
        ) : (
          <p className="mt-4 text-xs text-muted-foreground">{t("copilot.actions.noPermission")}</p>
        )
      ) : null}
    </article>
  );
}

function DraftBlock({ label, draft, muted = false }: { label: string; draft: { subject: string; message: string }; muted?: boolean }) {
  return (
    <div className={muted ? "rounded-lg border border-dashed border-border p-2.5 opacity-80" : "rounded-lg bg-muted/30 p-2.5"}>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-medium">{draft.subject}</p>
      <p className="mt-1 whitespace-pre-line text-sm leading-6">{draft.message}</p>
    </div>
  );
}
