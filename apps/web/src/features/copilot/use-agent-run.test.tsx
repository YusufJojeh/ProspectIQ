import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AgentAction, AgentRun } from "@/types/agent";

import { useAgentRun } from "./use-agent-run";

const NOW = "2026-09-19T10:00:00Z";

interface Server {
  runStatus: AgentRun["status"];
  actionStatus: AgentAction["status"];
  streamUrls: string[];
  /** One entry per stream connection; the status the server reports afterwards is `runStatus`. */
  streamBodies: string[];
  approveCalls: number;
}

function frame(seq: number, type: string, payload: Record<string, unknown> = {}): string {
  const data = JSON.stringify({ event_id: `e${seq}`, seq, event_type: type, payload, created_at: NOW });
  return `id: ${seq}\nevent: ${type}\ndata: ${data}\n\n`;
}

function run(server: Server): AgentRun {
  return {
    run_id: "arun_1",
    status: server.runStatus,
    profile: "sales_copilot",
    stop_reason: null,
    lead_id: null,
    goal: "g",
    step_count: 1,
    tool_call_count: 0,
    external_search_count: 0,
    crawl_count: 0,
    write_proposal_count: 1,
    final_answer:
      server.runStatus === "completed"
        ? {
            answer: "Done.",
            confidence: 0.5,
            research_coverage: 0.5,
            evidence_refs: [],
            knowledge_refs: [],
            opportunities: [],
            risks: [],
            recommended_actions: [],
            completed_actions: [],
            pending_actions: [],
            follow_up_questions: [],
          }
        : null,
    error_code: null,
    error_message: null,
    created_at: NOW,
    updated_at: NOW,
    completed_at: null,
  };
}

function action(server: Server): AgentAction {
  return {
    action_id: "aact_1",
    run_id: "arun_1",
    tool_name: "add_lead_note",
    resource_type: "lead",
    resource_id: "l1",
    preview: { note: "hello" },
    risk_level: "low",
    status: server.actionStatus,
    result: null,
    failure_code: null,
    failure_message: null,
    expires_at: NOW,
    approved_at: null,
    executed_at: null,
    created_at: NOW,
  };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

function installFetch(server: Server) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost");
    const path = url.pathname;
    const method = init?.method ?? "GET";
    if (method === "POST" && path.endsWith("/runs")) return json(run(server), 201);
    if (path.endsWith("/stream")) {
      server.streamUrls.push(`${path}${url.search}`);
      const body = server.streamBodies.shift() ?? "";
      return new Response(body, { status: 200, headers: { "content-type": "text/event-stream" } });
    }
    if (path.endsWith("/events")) return json({ run_id: "arun_1", events: [] });
    if (path.endsWith("/approve")) {
      server.approveCalls += 1;
      server.actionStatus = "executed";
      server.runStatus = "completed";
      return json(action(server));
    }
    if (path.endsWith("/agent/actions")) {
      return json({ items: [action(server)], page: 1, per_page: 50, total: 1 });
    }
    if (path.endsWith("/runs/arun_1")) return json(run(server));
    return json({ detail: "unexpected" }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useAgentRun", () => {
  let server: Server;

  beforeEach(() => {
    server = { runStatus: "running", actionStatus: "pending", streamUrls: [], streamBodies: [], approveCalls: 0 };
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("pauses on approval, keeps the action pending, and resumes the same run after the server confirms", async () => {
    server.streamBodies.push(
      frame(1, "agent_started") + frame(2, "action_proposed") + frame(3, "waiting_for_approval"),
    );
    // The server has already paused the run by the time the stream closes.
    server.runStatus = "waiting_for_approval";
    installFetch(server);

    const { result } = renderHook(() => useAgentRun(), { wrapper });
    await act(async () => {
      await result.current.start({ goal: "Why?" });
    });

    await waitFor(() => expect(result.current.state.phase).toBe("waiting_for_approval"));
    expect(result.current.state.actions["aact_1"]?.status).toBe("pending");
    expect(server.approveCalls).toBe(0);

    await act(async () => {
      await result.current.approve("aact_1");
    });

    await waitFor(() => expect(result.current.state.phase).toBe("completed"));
    expect(result.current.state.actions["aact_1"]?.status).toBe("executed");
    expect(server.approveCalls).toBe(1);
    // Same-run resume: approval never opened a second stream or a second run.
    expect(server.streamUrls).toHaveLength(1);
  });

  it("reconnects from the last seen sequence when the stream closes while the run is still active", async () => {
    server.streamBodies.push(frame(1, "agent_started") + frame(2, "tool_requested", { tool_name: "get_lead_context" }));
    server.streamBodies.push(frame(3, "agent_completed"));
    installFetch(server);
    // The run is still working when the first connection drops; it completes during the second.
    const originalShift = server.streamBodies.shift.bind(server.streamBodies);
    server.streamBodies.shift = () => {
      const body = originalShift();
      if (server.streamUrls.length === 2) server.runStatus = "completed";
      return body;
    };

    const { result } = renderHook(() => useAgentRun(), { wrapper });
    await act(async () => {
      await result.current.start({ goal: "Why?" });
    });

    await waitFor(() => expect(result.current.state.phase).toBe("completed"), { timeout: 5000 });
    expect(server.streamUrls[0]).not.toContain("after_seq");
    expect(server.streamUrls[1]).toContain("after_seq=2");
  });

  it("reports a failed start as an error state and never as a completed run", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json({ detail: "Forbidden" }, 403)),
    );
    const { result } = renderHook(() => useAgentRun(), { wrapper });
    await act(async () => {
      await result.current.start({ goal: "Why?" });
    });

    await waitFor(() => expect(result.current.state.phase).toBe("failed"));
    expect(result.current.state.errorKey).toBe("copilot.errors.forbidden");
    expect(result.current.state.run).toBeNull();
  });
});
