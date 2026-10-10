import { describe, expect, it } from "vitest";

import type { AgentAction, AgentEvent, AgentRun } from "@/types/agent";

import {
  copilotReducer,
  describeEvent,
  initialCopilotState,
  parseFinalAnswer,
  pendingActions,
  toolActivityKey,
  type CopilotState,
} from "./agent-state";

function run(overrides: Partial<AgentRun> = {}): AgentRun {
  return {
    run_id: "arun_1",
    status: "running",
    profile: "sales_copilot",
    stop_reason: null,
    lead_id: null,
    goal: "g",
    step_count: 0,
    tool_call_count: 0,
    external_search_count: 0,
    crawl_count: 0,
    write_proposal_count: 0,
    final_answer: null,
    error_code: null,
    error_message: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    completed_at: null,
    ...overrides,
  };
}

function event(seq: number, type: string, payload: Record<string, unknown> = {}): AgentEvent {
  return {
    event_id: `aev_${seq}`,
    seq,
    event_type: type,
    payload,
    created_at: "2026-01-01T00:00:00Z",
  };
}

function action(
  id: string,
  created: string,
  status: AgentAction["status"] = "pending",
): AgentAction {
  return {
    action_id: id,
    run_id: "arun_1",
    tool_name: "add_lead_note",
    resource_type: "lead",
    resource_id: "lead_1",
    preview: {},
    risk_level: "low",
    status,
    result: null,
    failure_code: null,
    failure_message: null,
    expires_at: "2026-01-02T00:00:00Z",
    approved_at: null,
    executed_at: null,
    created_at: created,
  };
}

function started(): CopilotState {
  const s = copilotReducer(initialCopilotState, { type: "start", goal: "g" });
  return copilotReducer(s, { type: "run_created", run: run() });
}

describe("copilotReducer", () => {
  it("moves starting -> running when the run is created", () => {
    expect(started().phase).toBe("running");
  });

  it("drops duplicate and out-of-order events by seq", () => {
    let s = started();
    s = copilotReducer(s, {
      type: "events",
      events: [event(2, "tool_requested", { tool_name: "get_lead_context" }), event(1, "agent_started")],
    });
    s = copilotReducer(s, {
      type: "events",
      events: [event(1, "agent_started"), event(2, "tool_requested")],
    });
    expect(s.lastSeq).toBe(2);
    expect(s.activity.map((a) => a.seq)).toEqual([1, 2]);
  });

  it("keeps terminal phases sticky against late snapshots and events", () => {
    let s = started();
    s = copilotReducer(s, { type: "events", events: [event(1, "agent_completed")] });
    expect(s.phase).toBe("completed");
    s = copilotReducer(s, { type: "run_synced", run: run({ status: "running" }) });
    s = copilotReducer(s, { type: "events", events: [event(2, "agent_started")] });
    s = copilotReducer(s, { type: "resuming" });
    expect(s.phase).toBe("completed");
  });

  it("never marks an action executed from a proposal or approval", () => {
    let s = started();
    s = copilotReducer(s, { type: "actions_synced", actions: [action("a1", "1")] });
    s = copilotReducer(s, {
      type: "events",
      events: [event(1, "action_proposed", { action_id: "a1" }), event(2, "waiting_for_approval")],
    });
    expect(s.actions.a1.status).toBe("pending");
    expect(s.phase).toBe("waiting_for_approval");
    s = copilotReducer(s, { type: "decision_started", actionId: "a1", decision: "approve" });
    expect(s.actions.a1.status).toBe("pending");
    s = copilotReducer(s, {
      type: "events",
      events: [event(3, "action_approved", { action_id: "a1" })],
    });
    expect(s.actions.a1.status).toBe("approved");
    s = copilotReducer(s, {
      type: "events",
      events: [event(4, "action_completed", { action_id: "a1" })],
    });
    expect(s.actions.a1.status).toBe("executed");
  });

  it("orders actions by creation and lists only pending ones for approval", () => {
    let s = started();
    s = copilotReducer(s, {
      type: "actions_synced",
      actions: [action("b", "2"), action("a", "1"), action("c", "3", "executed")],
    });
    expect(pendingActions(s).map((a) => a.action_id)).toEqual(["a", "b"]);
  });

  it("clears the in-flight decision once the server reports a settled status", () => {
    let s = started();
    s = copilotReducer(s, { type: "actions_synced", actions: [action("a1", "1")] });
    s = copilotReducer(s, { type: "decision_started", actionId: "a1", decision: "reject" });
    s = copilotReducer(s, { type: "action_synced", action: action("a1", "1", "rejected") });
    expect(s.decisions).toEqual({});
  });

  it("resumes the same run after approval", () => {
    let s = started();
    s = copilotReducer(s, { type: "events", events: [event(1, "waiting_for_approval")] });
    s = copilotReducer(s, { type: "resuming" });
    expect(s.phase).toBe("resuming");
    s = copilotReducer(s, { type: "events", events: [event(2, "agent_resumed")] });
    expect(s.phase).toBe("running");
    expect(s.runId).toBe("arun_1");
  });

  it("ignores snapshots for a different run", () => {
    const s = started();
    const next = copilotReducer(s, {
      type: "run_synced",
      run: run({ run_id: "arun_2", status: "failed" }),
    });
    expect(next).toBe(s);
  });

  it("tracks retrieved knowledge separately from activity", () => {
    let s = started();
    s = copilotReducer(s, {
      type: "events",
      events: [
        event(1, "knowledge_selected", {
          citations: [
            { document_id: "kdoc_1", document_title: "Case study", document_type: "case_studies" },
          ],
        }),
      ],
    });
    expect(s.knowledge.kdoc_1.title).toBe("Case study");
    expect(s.activity).toHaveLength(0);
  });
});

describe("describeEvent", () => {
  it("never exposes tool arguments or raw payloads", () => {
    const d = describeEvent(
      event(1, "tool_requested", { tool_name: "search_web_tavily", arguments: { q: "secret" } }),
    );
    expect(JSON.stringify(d)).not.toContain("secret");
    expect(d.activity?.labelKey).toBe("copilot.activity.researching");
  });

  it("hides internal plumbing events", () => {
    for (const type of ["model_started", "assistant_delta", "heartbeat", "tool_completed"]) {
      expect(describeEvent(event(1, type)).activity).toBeNull();
    }
  });

  it("maps unknown tools to a neutral label", () => {
    expect(toolActivityKey("something_new")).toBe("copilot.activity.working");
  });
});

describe("parseFinalAnswer", () => {
  it("rejects non-answers and clamps out-of-range numbers", () => {
    expect(parseFinalAnswer(null)).toBeNull();
    expect(parseFinalAnswer({ nope: 1 })).toBeNull();
    const parsed = parseFinalAnswer({
      answer: "x",
      confidence: 7,
      evidence_refs: ["ev_1", 3],
      risks: "bad",
    });
    expect(parsed?.confidence).toBe(1);
    expect(parsed?.evidence_refs).toEqual(["ev_1"]);
    expect(parsed?.risks).toEqual([]);
  });
});
