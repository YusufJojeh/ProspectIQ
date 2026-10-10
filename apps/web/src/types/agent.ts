/**
 * Contracts for the Agent runtime (`/api/v1/agent/*`), mirroring
 * apps/api/app/modules/agents/schemas.py.
 */

export type AgentRunStatus =
  | "queued"
  | "running"
  | "waiting_for_approval"
  | "completed"
  | "failed"
  | "cancelled"
  | "expired";

export type AgentActionStatus =
  | "pending"
  | "approved"
  | "executing"
  | "executed"
  | "rejected"
  | "expired"
  | "failed"
  | "cancelled";

export type AgentRiskLevel = "low" | "medium" | "high" | "blocked";

export type AgentProfileKey =
  | "research"
  | "sales_copilot"
  | "read_only"
  | "admin_assistant";

/** Backend-grounded final answer (AgentFinalAnswer). */
export interface AgentFinalAnswer {
  answer: string;
  lead_id: string | null;
  confidence: number;
  research_coverage: number;
  /** Lead evidence ids (`ev_…`, `rce_…`, `rrun_…`). Never internal knowledge. */
  evidence_refs: string[];
  /** Internal Sales Knowledge document ids. Never lead evidence. */
  knowledge_refs: string[];
  opportunities: string[];
  risks: string[];
  recommended_actions: string[];
  /** `"<tool>:<action_id>"` */
  completed_actions: string[];
  /** `"<tool>:<action_id>"` */
  pending_actions: string[];
  follow_up_questions: string[];
}

export interface AgentRunCreateRequest {
  goal: string;
  lead_id?: string | null;
  profile?: AgentProfileKey;
}

export interface AgentRun {
  run_id: string;
  status: AgentRunStatus;
  profile: string;
  stop_reason: string | null;
  lead_id: string | null;
  goal: string;
  step_count: number;
  tool_call_count: number;
  external_search_count: number;
  crawl_count: number;
  write_proposal_count: number;
  /** Validated with `parseFinalAnswer` before use; the wire type is loose. */
  final_answer: Record<string, unknown> | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface AgentEvent {
  event_id: string;
  seq: number;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface AgentEventListResponse {
  run_id: string;
  events: AgentEvent[];
}

export interface AgentAction {
  action_id: string;
  /** Public run id (`arun_…`). */
  run_id: string;
  tool_name: string;
  resource_type: string;
  resource_id: string;
  /** Exact, non-mutating preview of what approval will execute. */
  preview: Record<string, unknown>;
  risk_level: AgentRiskLevel;
  status: AgentActionStatus;
  result: Record<string, unknown> | null;
  failure_code: string | null;
  failure_message: string | null;
  expires_at: string;
  approved_at: string | null;
  executed_at: string | null;
  created_at: string;
}

export interface AgentActionListResponse {
  items: AgentAction[];
  page: number;
  per_page: number;
  total: number;
}

export interface AgentActionRejectRequest {
  reason?: string | null;
}

export const TERMINAL_RUN_STATUSES: readonly AgentRunStatus[] = [
  "completed",
  "failed",
  "cancelled",
  "expired",
];

export function isTerminalRunStatus(status: AgentRunStatus): boolean {
  return TERMINAL_RUN_STATUSES.includes(status);
}
