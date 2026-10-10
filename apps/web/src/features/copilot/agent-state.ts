import {
  isTerminalRunStatus,
  type AgentAction,
  type AgentActionStatus,
  type AgentEvent,
  type AgentFinalAnswer,
  type AgentRun,
  type AgentRunStatus,
} from "@/types/agent";

/**
 * One coherent Copilot state, driven by backend status.
 *
 * The UI never keeps independent `isLoading` / `isWaiting` / `isDone` flags:
 * every view is a function of `phase`, which can only move along the
 * transitions below. Terminal phases are sticky, so a late HTTP response or a
 * replayed event can never resurrect a finished run.
 */
export type CopilotPhase =
  | "idle"
  | "starting"
  | "running"
  | "waiting_for_approval"
  | "resuming"
  | "completed"
  | "failed"
  | "cancelled"
  | "expired";

export type ConnectionState =
  | "idle"
  | "connecting"
  | "open"
  | "reconnecting"
  | "closed"
  | "failed";

export type ActivityTone = "progress" | "success" | "warning" | "danger" | "info";

export interface ActivityItem {
  seq: number;
  eventId: string;
  /** i18n key under `copilot.activity.*`; never raw backend text. */
  labelKey: string;
  params?: Record<string, string | number>;
  tone: ActivityTone;
  createdAt: string;
}

export interface KnowledgeDocRef {
  id: string;
  title: string;
  documentType: string;
}

export interface CopilotState {
  phase: CopilotPhase;
  runId: string | null;
  goal: string;
  run: AgentRun | null;
  /** Highest event seq applied; anything <= this is a duplicate. */
  lastSeq: number;
  activity: ActivityItem[];
  actions: Record<string, AgentAction>;
  actionOrder: string[];
  /** Approve/reject requests currently in flight, by action id. */
  decisions: Record<string, "approve" | "reject">;
  /** Documents the run actually retrieved, keyed by document id. */
  knowledge: Record<string, KnowledgeDocRef>;
  budgetExhausted: string | null;
  connection: ConnectionState;
  /** Translation key under `copilot.errors.*`, or null. */
  errorKey: string | null;
}

export const MAX_ACTIVITY_ITEMS = 200;

export const initialCopilotState: CopilotState = {
  phase: "idle",
  runId: null,
  goal: "",
  run: null,
  lastSeq: 0,
  activity: [],
  actions: {},
  actionOrder: [],
  decisions: {},
  knowledge: {},
  budgetExhausted: null,
  connection: "idle",
  errorKey: null,
};

export type CopilotAction =
  | { type: "start"; goal: string }
  | { type: "run_created"; run: AgentRun }
  | { type: "run_synced"; run: AgentRun }
  | { type: "events"; events: AgentEvent[] }
  | { type: "actions_synced"; actions: AgentAction[] }
  | { type: "action_synced"; action: AgentAction }
  | { type: "decision_started"; actionId: string; decision: "approve" | "reject" }
  | { type: "decision_settled"; actionId: string }
  | { type: "resuming" }
  | { type: "connection"; state: ConnectionState }
  | { type: "failed"; errorKey: string }
  | { type: "reset" };

const TERMINAL_PHASES: readonly CopilotPhase[] = [
  "completed",
  "failed",
  "cancelled",
  "expired",
];

export function isTerminalPhase(phase: CopilotPhase): boolean {
  return TERMINAL_PHASES.includes(phase);
}

export function phaseFromStatus(status: AgentRunStatus): CopilotPhase {
  switch (status) {
    case "queued":
    case "running":
      return "running";
    case "waiting_for_approval":
      return "waiting_for_approval";
    case "completed":
    case "failed":
    case "cancelled":
    case "expired":
      return status;
  }
}

/** Phase after an HTTP status snapshot. Terminal phases are never left. */
function nextPhaseFromSnapshot(current: CopilotPhase, status: AgentRunStatus): CopilotPhase {
  if (isTerminalPhase(current)) return current;
  return phaseFromStatus(status);
}

const ACTION_STATUS_BY_EVENT: Record<string, AgentActionStatus> = {
  action_approved: "approved",
  action_executing: "executing",
  action_completed: "executed",
  action_failed: "failed",
  action_rejected: "rejected",
};

function str(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

const RESEARCH_TOOLS = new Set([
  "search_web_tavily",
  "search_google_serpapi",
  "crawl_company_site",
  "crawl_reviews",
  "refresh_lead_research",
]);
const EVIDENCE_TOOLS = new Set([
  "get_lead_context",
  "get_lead_notes",
  "get_lead_activity",
  "get_contact_channels",
  "get_existing_evidence",
  "get_evidence_graph",
  "get_research_history",
  "get_previous_research",
  "get_score_breakdown",
  "get_outreach_history",
  "compare_evidence",
]);
const KNOWLEDGE_TOOLS = new Set([
  "get_service_catalog",
  "search_sales_knowledge",
  "get_relevant_case_studies",
  "get_sales_playbook",
  "match_capabilities_to_lead",
]);

/** Maps a tool name to a polished, user-facing activity label key. */
export function toolActivityKey(toolName: string | null): string {
  if (!toolName) return "copilot.activity.working";
  if (RESEARCH_TOOLS.has(toolName)) return "copilot.activity.researching";
  if (EVIDENCE_TOOLS.has(toolName)) return "copilot.activity.reviewingEvidence";
  if (toolName === "get_delta_changes") return "copilot.activity.checkingChanges";
  if (toolName === "get_icp_profile") return "copilot.activity.checkingIcp";
  if (KNOWLEDGE_TOOLS.has(toolName)) return "copilot.activity.searchingKnowledge";
  if (toolName === "draft_outreach" || toolName === "save_outreach_draft") {
    return "copilot.activity.preparingDraft";
  }
  if (toolName === "add_lead_note") return "copilot.activity.proposingNote";
  if (toolName === "create_follow_up" || toolName === "create_lead_task") {
    return "copilot.activity.proposingFollowUp";
  }
  if (toolName === "update_lead_stage") return "copilot.activity.proposingStage";
  if (toolName === "update_lead_tags") return "copilot.activity.proposingTags";
  if (toolName === "request_deep_research") return "copilot.activity.proposingResearch";
  if (toolName === "draft_proposal") return "copilot.activity.proposingProposal";
  if (toolName.startsWith("send_")) return "copilot.activity.proposingSend";
  return "copilot.activity.working";
}

interface DescribedEvent {
  activity: ActivityItem | null;
  knowledge: KnowledgeDocRef[];
}

function knowledgeFromPayload(payload: Record<string, unknown>): KnowledgeDocRef[] {
  const citations = payload.citations;
  if (!Array.isArray(citations)) return [];
  const docs: KnowledgeDocRef[] = [];
  for (const entry of citations) {
    if (typeof entry !== "object" || entry === null) continue;
    const record = entry as Record<string, unknown>;
    const id = str(record.document_id);
    const title = str(record.document_title);
    if (id && title) {
      docs.push({ id, title, documentType: str(record.document_type) ?? "" });
    }
  }
  return docs;
}

/**
 * Translates one backend event into a user-facing activity line. Tool
 * payloads, arguments and model reasoning are never surfaced: only the
 * category of work and its outcome.
 */
export function describeEvent(event: AgentEvent): DescribedEvent {
  const base = { seq: event.seq, eventId: event.event_id, createdAt: event.created_at };
  const line = (
    labelKey: string,
    tone: ActivityTone,
    params?: Record<string, string | number>,
  ): DescribedEvent => ({
    activity: { ...base, labelKey, tone, ...(params ? { params } : {}) },
    knowledge: [],
  });
  const p = event.payload;

  switch (event.event_type) {
    case "agent_started":
      return line("copilot.activity.started", "info");
    case "tool_requested":
      return line(toolActivityKey(str(p.tool_name)), "progress");
    case "tool_failed":
      return line("copilot.activity.stepFailed", "warning");
    case "rag_search_started":
      return line("copilot.activity.searchingKnowledge", "progress");
    case "rag_search_completed": {
      const count = num(p.result_count) ?? 0;
      if (count === 0) return line("copilot.activity.noKnowledgeMatch", "info");
      return p.degraded === true
        ? line("copilot.activity.knowledgeFoundDegraded", "warning", { count })
        : line("copilot.activity.knowledgeFound", "success", { count });
    }
    case "knowledge_selected":
      return { activity: null, knowledge: knowledgeFromPayload(p) };
    case "action_proposed":
      return line("copilot.activity.actionPrepared", "info");
    case "waiting_for_approval":
      return line("copilot.activity.waitingForApproval", "warning");
    case "action_approved":
      return line("copilot.activity.actionApproved", "info");
    case "action_executing":
      return line("copilot.activity.actionExecuting", "progress");
    case "action_completed":
      return line("copilot.activity.actionCompleted", "success");
    case "action_failed":
      return line("copilot.activity.actionFailed", "danger");
    case "action_rejected":
      return line("copilot.activity.actionRejected", "info");
    case "agent_resumed":
      return line("copilot.activity.resumed", "progress");
    case "agent_completed":
      return line("copilot.activity.completed", "success");
    case "agent_failed":
      return line("copilot.activity.failed", "danger");
    case "agent_cancelled":
      return line("copilot.activity.cancelled", "info");
    case "budget_exhausted":
      return line("copilot.activity.budgetReached", "warning");
    default:
      // model_started, model_completed, assistant_delta, heartbeat,
      // final_evidence_ref_dropped, tool_started, tool_completed: internal
      // plumbing, deliberately not shown.
      return { activity: null, knowledge: [] };
  }
}

function phaseAfterEvent(current: CopilotPhase, event: AgentEvent): CopilotPhase {
  if (isTerminalPhase(current)) return current;
  switch (event.event_type) {
    case "agent_started":
    case "agent_resumed":
      return "running";
    case "waiting_for_approval":
      return "waiting_for_approval";
    case "agent_completed":
      return "completed";
    case "agent_failed":
      return "failed";
    case "agent_cancelled":
      return "cancelled";
    default:
      // Work continuing after a decision means the run is running again.
      if (current === "resuming" && event.event_type.startsWith("tool_")) {
        return "running";
      }
      return current;
  }
}

function applyEvents(state: CopilotState, incoming: AgentEvent[]): CopilotState {
  const fresh = incoming
    .filter((event) => event.seq > state.lastSeq)
    .sort((a, b) => a.seq - b.seq);
  if (fresh.length === 0) return state;

  let phase = state.phase;
  let actions = state.actions;
  let knowledge = state.knowledge;
  let budgetExhausted = state.budgetExhausted;
  const activity = [...state.activity];
  const seen = new Set<number>();

  for (const event of fresh) {
    if (seen.has(event.seq)) continue;
    seen.add(event.seq);
    phase = phaseAfterEvent(phase, event);

    const described = describeEvent(event);
    if (described.activity) activity.push(described.activity);
    if (described.knowledge.length > 0) {
      knowledge = { ...knowledge };
      for (const doc of described.knowledge) knowledge[doc.id] = doc;
    }
    if (event.event_type === "budget_exhausted") {
      budgetExhausted = str(event.payload.budget) ?? "budget";
    }

    const nextStatus = ACTION_STATUS_BY_EVENT[event.event_type];
    const actionId = str(event.payload.action_id);
    if (nextStatus && actionId && actions[actionId]) {
      actions = { ...actions, [actionId]: { ...actions[actionId], status: nextStatus } };
    }
  }

  return {
    ...state,
    phase,
    actions,
    knowledge,
    budgetExhausted,
    lastSeq: fresh[fresh.length - 1].seq,
    activity: activity.slice(-MAX_ACTIVITY_ITEMS),
  };
}

function mergeActions(state: CopilotState, incoming: AgentAction[]): CopilotState {
  const actions = { ...state.actions };
  const order = [...state.actionOrder];
  for (const action of incoming) {
    if (!(action.action_id in actions)) order.push(action.action_id);
    actions[action.action_id] = action;
  }
  // Creation order is the approval order; keep it stable across refetches.
  order.sort((a, b) =>
    actions[a].created_at === actions[b].created_at
      ? a.localeCompare(b)
      : actions[a].created_at.localeCompare(actions[b].created_at),
  );
  return { ...state, actions, actionOrder: order };
}

export function copilotReducer(state: CopilotState, action: CopilotAction): CopilotState {
  switch (action.type) {
    case "reset":
      return initialCopilotState;
    case "start":
      return { ...initialCopilotState, phase: "starting", goal: action.goal };
    case "run_created":
      return {
        ...state,
        run: action.run,
        runId: action.run.run_id,
        goal: action.run.goal,
        phase: nextPhaseFromSnapshot("starting", action.run.status),
        errorKey: null,
      };
    case "run_synced":
      if (state.runId !== null && action.run.run_id !== state.runId) return state;
      return {
        ...state,
        run: action.run,
        runId: action.run.run_id,
        phase: nextPhaseFromSnapshot(state.phase, action.run.status),
        // A settled status supersedes an in-flight "resuming".
        decisions: isTerminalRunStatus(action.run.status) ? {} : state.decisions,
      };
    case "events":
      return applyEvents(state, action.events);
    case "actions_synced":
    case "action_synced": {
      const list = action.type === "actions_synced" ? action.actions : [action.action];
      const merged = mergeActions(state, list);
      // The action carries the server's status; drop decision flags it settled.
      const decisions = { ...merged.decisions };
      for (const item of list) {
        if (item.status !== "pending") delete decisions[item.action_id];
      }
      return { ...merged, decisions };
    }
    case "decision_started":
      return { ...state, decisions: { ...state.decisions, [action.actionId]: action.decision } };
    case "decision_settled": {
      const decisions = { ...state.decisions };
      delete decisions[action.actionId];
      return { ...state, decisions };
    }
    case "resuming":
      return isTerminalPhase(state.phase) ? state : { ...state, phase: "resuming" };
    case "connection":
      return { ...state, connection: action.state };
    case "failed":
      return {
        ...state,
        phase: isTerminalPhase(state.phase) ? state.phase : "failed",
        errorKey: action.errorKey,
      };
  }
}

export function pendingActions(state: CopilotState): AgentAction[] {
  return state.actionOrder
    .map((id) => state.actions[id])
    .filter((action) => action.status === "pending");
}

export function isBusy(phase: CopilotPhase): boolean {
  return phase === "starting" || phase === "running" || phase === "resuming";
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((x): x is string => typeof x === "string") : [];
}

/** Validates the loosely-typed wire object before the UI trusts any field. */
export function parseFinalAnswer(raw: Record<string, unknown> | null): AgentFinalAnswer | null {
  if (!raw || typeof raw.answer !== "string") return null;
  const confidence = num(raw.confidence);
  const coverage = num(raw.research_coverage);
  return {
    answer: raw.answer,
    lead_id: str(raw.lead_id),
    confidence: confidence === null ? 0 : Math.min(1, Math.max(0, confidence)),
    research_coverage: coverage === null ? 0 : Math.min(1, Math.max(0, coverage)),
    evidence_refs: stringList(raw.evidence_refs),
    knowledge_refs: stringList(raw.knowledge_refs),
    opportunities: stringList(raw.opportunities),
    risks: stringList(raw.risks),
    recommended_actions: stringList(raw.recommended_actions),
    completed_actions: stringList(raw.completed_actions),
    pending_actions: stringList(raw.pending_actions),
    follow_up_questions: stringList(raw.follow_up_questions),
  };
}
