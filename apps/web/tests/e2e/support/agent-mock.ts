import type { Page, Route } from "@playwright/test";

const RUN_ID = "arun_e2e";
const ACTION_ID = "aact_e2e_note";
const NOW = "2026-09-19T10:00:00Z";

type ActionStatus = "pending" | "executed" | "rejected";

export interface AgentMock {
  runStatus: "running" | "waiting_for_approval" | "completed";
  actionStatus: ActionStatus;
  approveCalls: number;
  rejectCalls: number;
  approveDelayMs: number;
}

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

function frame(seq: number, eventType: string, payload: Record<string, unknown> = {}) {
  const data = JSON.stringify({ event_id: `evt_${seq}`, seq, event_type: eventType, payload, created_at: NOW });
  return `id: ${seq}\nevent: ${eventType}\ndata: ${data}\n\n`;
}

function finalAnswer() {
  return {
    answer: "Acme Dental is a strong fit: it has no online booking and a weak review response rate.",
    lead_id: null,
    confidence: 0.72,
    research_coverage: 0.6,
    evidence_refs: [],
    knowledge_refs: ["kdoc_case_study"],
    opportunities: ["Add online booking"],
    risks: ["Only one location"],
    recommended_actions: ["Open with the booking gap"],
    completed_actions: ["add_lead_note:" + ACTION_ID],
    pending_actions: [],
    follow_up_questions: ["Who owns the website?"],
  };
}

function runBody(mock: AgentMock) {
  return {
    run_id: RUN_ID,
    status: mock.runStatus,
    profile: "sales_copilot",
    stop_reason: null,
    lead_id: null,
    goal: "Why is this a good fit?",
    step_count: 2,
    tool_call_count: 1,
    external_search_count: 0,
    crawl_count: 0,
    write_proposal_count: 1,
    final_answer: mock.runStatus === "completed" ? finalAnswer() : null,
    error_code: null,
    error_message: null,
    created_at: NOW,
    updated_at: NOW,
    completed_at: mock.runStatus === "completed" ? NOW : null,
  };
}

function actionBody(mock: AgentMock) {
  return {
    action_id: ACTION_ID,
    run_id: RUN_ID,
    tool_name: "add_lead_note",
    resource_type: "lead",
    resource_id: "lead_1",
    preview: { lead_id: "lead_1", note: "Booking gap confirmed on the website." },
    risk_level: "low",
    status: mock.actionStatus,
    result: null,
    failure_code: null,
    failure_message: null,
    expires_at: "2026-09-20T10:00:00Z",
    approved_at: null,
    executed_at: mock.actionStatus === "executed" ? NOW : null,
    created_at: NOW,
  };
}

export async function installAgentMock(page: Page, overrides: Partial<AgentMock> = {}): Promise<AgentMock> {
  const mock: AgentMock = {
    runStatus: "running",
    actionStatus: "pending",
    approveCalls: 0,
    rejectCalls: 0,
    approveDelayMs: 0,
    ...overrides,
  };

  await page.route("**/api/v1/agent/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();

    if (method === "POST" && path.endsWith("/agent/runs")) return json(route, runBody(mock), 201);
    if (path.endsWith(`/runs/${RUN_ID}/stream`)) {
      // The server pauses the run once it has proposed a write, then closes the stream.
      mock.runStatus = mock.runStatus === "completed" ? "completed" : "waiting_for_approval";
      const frames =
        frame(1, "agent_started") +
        frame(2, "tool_requested", { tool_name: "get_lead_context" }) +
        frame(3, "action_proposed", { action_id: ACTION_ID, tool_name: "add_lead_note" }) +
        frame(4, "waiting_for_approval", { action_id: ACTION_ID });
      return route.fulfill({ status: 200, contentType: "text/event-stream", body: frames });
    }
    if (path.endsWith(`/runs/${RUN_ID}/events`)) {
      return json(route, { run_id: RUN_ID, events: [] });
    }
    if (path.endsWith(`/runs/${RUN_ID}/cancel`)) {
      return json(route, runBody(mock));
    }
    if (path.endsWith(`/runs/${RUN_ID}`)) return json(route, runBody(mock));
    if (path.endsWith(`/actions/${ACTION_ID}/approve`)) {
      mock.approveCalls += 1;
      if (mock.approveDelayMs > 0) await new Promise((resolve) => setTimeout(resolve, mock.approveDelayMs));
      mock.actionStatus = "executed";
      mock.runStatus = "completed";
      return json(route, actionBody(mock));
    }
    if (path.endsWith(`/actions/${ACTION_ID}/reject`)) {
      mock.rejectCalls += 1;
      mock.actionStatus = "rejected";
      mock.runStatus = "completed";
      return json(route, actionBody(mock));
    }
    if (path.endsWith("/agent/actions")) {
      return json(route, { items: [actionBody(mock)], page: 1, per_page: 50, total: 1 });
    }
    return json(route, { detail: "not mocked" }, 404);
  });

  // Evidence graph is only fetched to label citations; an empty graph is a valid answer.
  await page.route("**/api/v1/research/**", async (route) => json(route, { detail: "not mocked" }, 404));
  return mock;
}

