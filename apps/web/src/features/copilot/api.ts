import { buildRequestUrl, request } from "@/lib/api-client";
import type {
  AgentAction,
  AgentActionListResponse,
  AgentActionRejectRequest,
  AgentEventListResponse,
  AgentRun,
  AgentRunCreateRequest,
} from "@/types/agent";

const BASE = "/api/v1/agent";

export function createAgentRun(payload: AgentRunCreateRequest) {
  return request<AgentRun>(`${BASE}/runs`, { method: "POST" }, payload);
}

export function getAgentRun(runId: string) {
  return request<AgentRun>(`${BASE}/runs/${runId}`);
}

export function cancelAgentRun(runId: string) {
  return request<AgentRun>(`${BASE}/runs/${runId}/cancel`, { method: "POST" });
}

export function listAgentEvents(runId: string) {
  return request<AgentEventListResponse>(`${BASE}/runs/${runId}/events`);
}

export function listAgentActions(params: {
  runId?: string;
  status?: string;
  page?: number;
  perPage?: number;
}) {
  const query = new URLSearchParams();
  if (params.runId) query.set("run_id", params.runId);
  if (params.status) query.set("status", params.status);
  query.set("page", String(params.page ?? 1));
  query.set("per_page", String(params.perPage ?? 50));
  return request<AgentActionListResponse>(`${BASE}/actions?${query.toString()}`);
}

export function approveAgentAction(actionId: string) {
  return request<AgentAction>(`${BASE}/actions/${actionId}/approve`, {
    method: "POST",
  });
}

export function rejectAgentAction(
  actionId: string,
  payload: AgentActionRejectRequest = {},
) {
  return request<AgentAction>(
    `${BASE}/actions/${actionId}/reject`,
    { method: "POST" },
    payload,
  );
}

/** URL of the live SSE stream. `afterSeq` resumes without replaying. */
export function agentStreamUrl(runId: string, afterSeq = 0): string {
  const suffix = afterSeq > 0 ? `?after_seq=${afterSeq}` : "";
  return buildRequestUrl(`${BASE}/runs/${runId}/stream${suffix}`);
}
