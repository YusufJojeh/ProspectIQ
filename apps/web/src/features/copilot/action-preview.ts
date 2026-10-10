import type { AgentAction, AgentActionStatus } from "@/types/agent";

export interface PreviewRow {
  /** i18n key under `copilot.preview.fields.*`. */
  labelKey: string;
  value: string;
  /** When set, the value is an i18n key rather than display text. */
  translate?: boolean;
  /** Long free text renders as a block instead of an inline value. */
  block?: boolean;
}

export interface DraftText {
  subject: string;
  message: string;
}

export interface ActionView {
  /** i18n key under `copilot.actions.*`. */
  titleKey: string;
  rows: PreviewRow[];
  /** Present for outreach draft edits: existing text (null when none) and the proposal. */
  draft: { current: DraftText | null; proposed: DraftText } | null;
  irreversible: boolean;
  /** Server-provided delivery caveat, shown verbatim to the approver. */
  deliveryNote: string | null;
}

const TITLE_BY_TOOL: Record<string, string> = {
  save_outreach_draft: "copilot.actions.saveDraft",
  add_lead_note: "copilot.actions.addNote",
  create_follow_up: "copilot.actions.followUp",
  create_lead_task: "copilot.actions.task",
  update_lead_stage: "copilot.actions.stage",
  update_lead_tags: "copilot.actions.tags",
  request_deep_research: "copilot.actions.research",
  draft_proposal: "copilot.actions.proposal",
  send_email: "copilot.actions.sendEmail",
  send_whatsapp: "copilot.actions.sendWhatsapp",
  send_linkedin_message: "copilot.actions.sendLinkedin",
};

/** Fields the approver never needs to see (internal ids). */
const HIDDEN_FIELDS = new Set(["lead_id", "outreach_message_id", "irreversible", "delivery", "activity_type"]);

function scalar(value: unknown): string | null {
  if (typeof value === "string") return value.trim() === "" ? null : value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    const items = value.filter((x): x is string | number => typeof x === "string" || typeof x === "number");
    return items.length > 0 ? items.join(", ") : null;
  }
  return null;
}

function asDraft(value: unknown): DraftText | null {
  if (typeof value !== "object" || value === null) return null;
  const record = value as Record<string, unknown>;
  if (typeof record.subject !== "string" || typeof record.message !== "string") return null;
  return { subject: record.subject, message: record.message };
}

function camelKey(field: string): string {
  return field.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
}

/** Fields whose values are long prose. */
const BLOCK_FIELDS = new Set(["note", "body", "message", "milestones", "pricing_basis"]);

/** Fields whose value is an enum the UI translates (`copilot.preview.values.<field>.<value>`). */
const TRANSLATED_FIELDS = new Set(["pricing_status"]);

/**
 * Builds the approver-facing view of an action preview. Every value is
 * rendered as a labelled field; nested objects and unknown structures are
 * dropped rather than dumped as JSON.
 */
export function buildActionView(action: AgentAction): ActionView {
  const preview = action.preview;
  const draft = asDraft(preview.proposed);
  const rows: PreviewRow[] = [];

  if (!draft) {
    for (const [field, raw] of Object.entries(preview)) {
      if (HIDDEN_FIELDS.has(field)) continue;
      // A list shown as a block reads one item per line.
      const value =
        BLOCK_FIELDS.has(field) && Array.isArray(raw)
          ? scalar(raw.filter((item): item is string => typeof item === "string").join("\n"))
          : scalar(raw);
      if (value === null) continue;
      const translated = TRANSLATED_FIELDS.has(field);
      rows.push({
        labelKey: `copilot.preview.fields.${camelKey(field)}`,
        value: translated ? `copilot.preview.values.${camelKey(field)}.${value}` : value,
        ...(translated ? { translate: true } : {}),
        ...(BLOCK_FIELDS.has(field) ? { block: true } : {}),
      });
    }
  }

  return {
    titleKey: TITLE_BY_TOOL[action.tool_name] ?? "copilot.actions.generic",
    rows,
    draft: draft ? { current: asDraft(preview.current), proposed: draft } : null,
    irreversible: preview.irreversible === true,
    deliveryNote: typeof preview.delivery === "string" ? preview.delivery : null,
  };
}

/** The proposal a completed `draft_proposal` action created, if any. */
export function createdProposalId(action: AgentAction): string | null {
  if (action.tool_name !== "draft_proposal" || action.status !== "executed") return null;
  const id = action.result?.proposal_id;
  return typeof id === "string" && id !== "" ? id : null;
}

export function isSendTool(toolName: string): boolean {
  return toolName.startsWith("send_");
}

export type ActionTone = "warning" | "info" | "success" | "danger" | "neutral";

/** Badge tone and i18n label for a server-reported action status. */
export function actionStatusPresentation(status: AgentActionStatus): {
  labelKey: string;
  tone: ActionTone;
} {
  switch (status) {
    case "pending":
      return { labelKey: "copilot.status.pending", tone: "warning" };
    case "approved":
      return { labelKey: "copilot.status.approved", tone: "info" };
    case "executing":
      return { labelKey: "copilot.status.executing", tone: "info" };
    case "executed":
      return { labelKey: "copilot.status.executed", tone: "success" };
    case "rejected":
      return { labelKey: "copilot.status.rejected", tone: "neutral" };
    case "expired":
      return { labelKey: "copilot.status.expired", tone: "neutral" };
    case "failed":
      return { labelKey: "copilot.status.failed", tone: "danger" };
    case "cancelled":
      return { labelKey: "copilot.status.cancelled", tone: "neutral" };
  }
}
