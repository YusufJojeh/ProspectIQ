import { useCallback, useEffect, useReducer, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { ApiError, readToken } from "@/lib/api-client";
import { isTerminalRunStatus, type AgentEvent, type AgentProfileKey, type AgentRun } from "@/types/agent";

import {
  approveAgentAction,
  agentStreamUrl,
  cancelAgentRun,
  createAgentRun,
  getAgentRun,
  listAgentActions,
  listAgentEvents,
  rejectAgentAction,
} from "./api";
import {
  copilotReducer,
  initialCopilotState,
  type CopilotState,
} from "./agent-state";
import { SseParser, backoffDelayMs, frameToEvent } from "./sse";

const MAX_RECONNECT_ATTEMPTS = 6;
/** Events are applied in one reducer pass per flush, not one render each. */
const FLUSH_INTERVAL_MS = 60;

/** Maps a failure to a `copilot.errors.*` translation key. Never raw server text. */
export function errorKeyFor(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.statusCode) {
      case 400:
      case 422:
        return "copilot.errors.invalid";
      case 401:
        return "copilot.errors.session";
      case 403:
        return "copilot.errors.forbidden";
      case 404:
        return "copilot.errors.notFound";
      case 409:
        return "copilot.errors.conflict";
      case 429:
        return "copilot.errors.rateLimited";
      case 503:
        return "copilot.errors.unavailable";
      default:
        return error.statusCode >= 500
          ? "copilot.errors.server"
          : "copilot.errors.generic";
    }
  }
  return "copilot.errors.network";
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal.aborted) return resolve();
    const timer = setTimeout(resolve, ms);
    signal.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        resolve();
      },
      { once: true },
    );
  });
}

export interface StartRunInput {
  goal: string;
  leadId?: string | null;
  profile?: AgentProfileKey;
}

export interface UseAgentRun {
  state: CopilotState;
  start: (input: StartRunInput) => Promise<void>;
  cancel: () => Promise<void>;
  approve: (actionId: string) => Promise<void>;
  reject: (actionId: string, reason?: string) => Promise<void>;
  reset: () => void;
}

export function useAgentRun(): UseAgentRun {
  const [state, dispatch] = useReducer(copilotReducer, initialCopilotState);
  const queryClient = useQueryClient();

  // The stream loop and async handlers read the latest state through refs so
  // that a re-render never restarts the connection.
  const stateRef = useRef(state);
  stateRef.current = state;
  const abortRef = useRef<AbortController | null>(null);
  const pendingEvents = useRef<AgentEvent[]>([]);
  const flushTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const generation = useRef(0);
  /** Highest seq seen on any path; the resume point. Updated synchronously, unlike state. */
  const seqRef = useRef(0);

  const flush = useCallback(() => {
    flushTimer.current = null;
    if (pendingEvents.current.length === 0) return;
    const batch = pendingEvents.current;
    pendingEvents.current = [];
    dispatch({ type: "events", events: batch });
  }, []);

  const enqueue = useCallback(
    (event: AgentEvent) => {
      seqRef.current = Math.max(seqRef.current, event.seq);
      pendingEvents.current.push(event);
      if (flushTimer.current === null) {
        flushTimer.current = setTimeout(flush, FLUSH_INTERVAL_MS);
      }
    },
    [flush],
  );

  const invalidateLeadData = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["leads"] });
    void queryClient.invalidateQueries({ queryKey: ["lead"] });
    // Follow-ups and tasks are CRM activities.
    void queryClient.invalidateQueries({ queryKey: ["crm"] });
  }, [queryClient]);

  /** Re-reads everything the server considers authoritative for this run. */
  const syncFromServer = useCallback(
    async (runId: string, gen: number): Promise<AgentRun | null> => {
      const [run, actions, events] = await Promise.all([
        getAgentRun(runId),
        listAgentActions({ runId }),
        listAgentEvents(runId),
      ]);
      if (gen !== generation.current) return null;
      for (const event of events.events) seqRef.current = Math.max(seqRef.current, event.seq);
      // Events first so action statuses set by them are then overwritten by the
      // server's own action snapshot, which is the authority.
      dispatch({ type: "events", events: events.events });
      dispatch({ type: "actions_synced", actions: actions.items });
      dispatch({ type: "run_synced", run });
      if (actions.items.some((a) => a.status === "executed")) invalidateLeadData();
      return run;
    },
    [invalidateLeadData],
  );

  const stopStream = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  /** Streams until the server closes it; returns whether it ended cleanly. */
  const readStream = useCallback(
    async (runId: string, signal: AbortSignal): Promise<boolean> => {
      const token = readToken();
      const response = await fetch(agentStreamUrl(runId, seqRef.current), {
        headers: {
          Accept: "text/event-stream",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(seqRef.current > 0 ? { "Last-Event-ID": String(seqRef.current) } : {}),
        },
        signal,
      });
      if (!response.ok || !response.body) {
        throw new ApiError("Stream failed.", response.status);
      }
      dispatch({ type: "connection", state: "open" });
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      const parser = new SseParser();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) return true;
        for (const frame of parser.push(decoder.decode(value, { stream: true }))) {
          const event = frameToEvent(frame);
          // Heartbeats carry no state; they only keep proxies from idling out.
          if (event && event.event_type !== "heartbeat") enqueue(event);
        }
      }
    },
    [enqueue],
  );

  const runStreamLoop = useCallback(
    async (runId: string, gen: number) => {
      stopStream();
      const controller = new AbortController();
      abortRef.current = controller;
      let attempt = 0;
      while (!controller.signal.aborted && gen === generation.current) {
        dispatch({ type: "connection", state: attempt === 0 ? "connecting" : "reconnecting" });
        try {
          await readStream(runId, controller.signal);
          flush();
          attempt = 0;
          // The server closes the stream on completion or when parking for
          // approval. The snapshot decides whether to keep listening.
          const run = await syncFromServer(runId, gen);
          if (run === null) return;
          // Decide from the fetched snapshot: React state has not re-rendered yet.
          if (isTerminalRunStatus(run.status) || run.status === "waiting_for_approval") {
            dispatch({ type: "connection", state: "closed" });
            return;
          }
          // Still active but the server closed the stream (deadline, or no live
          // transport): pause briefly so this never becomes a tight loop.
          await sleep(1000, controller.signal);
        } catch (error) {
          if (controller.signal.aborted || gen !== generation.current) return;
          if (error instanceof ApiError && [401, 403, 404].includes(error.statusCode)) {
            dispatch({ type: "connection", state: "failed" });
            dispatch({ type: "failed", errorKey: errorKeyFor(error) });
            return;
          }
          attempt += 1;
          if (attempt > MAX_RECONNECT_ATTEMPTS) {
            dispatch({ type: "connection", state: "failed" });
            // Streaming is a convenience; the durable state is still fetchable.
            try {
              await syncFromServer(runId, gen);
            } catch (syncError) {
              dispatch({ type: "failed", errorKey: errorKeyFor(syncError) });
            }
            return;
          }
          dispatch({ type: "connection", state: "reconnecting" });
          await sleep(backoffDelayMs(attempt - 1), controller.signal);
        }
      }
    },
    [flush, readStream, stopStream, syncFromServer],
  );

  const start = useCallback(
    async ({ goal, leadId, profile }: StartRunInput) => {
      stopStream();
      generation.current += 1;
      const gen = generation.current;
      pendingEvents.current = [];
      seqRef.current = 0;
      dispatch({ type: "start", goal });
      try {
        const run = await createAgentRun({
          goal,
          lead_id: leadId ?? null,
          ...(profile ? { profile } : {}),
        });
        if (gen !== generation.current) return;
        dispatch({ type: "run_created", run });
        void runStreamLoop(run.run_id, gen);
      } catch (error) {
        if (gen !== generation.current) return;
        dispatch({ type: "failed", errorKey: errorKeyFor(error) });
      }
    },
    [runStreamLoop, stopStream],
  );

  const cancel = useCallback(async () => {
    const runId = stateRef.current.runId;
    if (!runId) return;
    try {
      const run = await cancelAgentRun(runId);
      dispatch({ type: "run_synced", run });
      stopStream();
      await syncFromServer(runId, generation.current);
    } catch (error) {
      dispatch({ type: "failed", errorKey: errorKeyFor(error) });
    }
  }, [stopStream, syncFromServer]);

  const decide = useCallback(
    async (actionId: string, decision: "approve" | "reject", reason?: string) => {
      const runId = stateRef.current.runId;
      const gen = generation.current;
      if (!runId || stateRef.current.decisions[actionId]) return;
      dispatch({ type: "decision_started", actionId, decision });
      dispatch({ type: "resuming" });
      try {
        // The status shown afterwards is whatever the server returns; nothing
        // is marked executed optimistically.
        const action =
          decision === "approve"
            ? await approveAgentAction(actionId)
            : await rejectAgentAction(actionId, reason ? { reason } : {});
        if (gen !== generation.current) return;
        dispatch({ type: "action_synced", action });
        await syncFromServer(runId, gen);
        if (action.status === "executed") invalidateLeadData();
      } catch (error) {
        if (gen !== generation.current) return;
        dispatch({ type: "decision_settled", actionId });
        dispatch({ type: "failed", errorKey: errorKeyFor(error) });
        // A 409 usually means another tab already decided; show the truth.
        try {
          await syncFromServer(runId, gen);
        } catch {
          /* the error above already tells the user */
        }
      }
    },
    [invalidateLeadData, syncFromServer],
  );

  const approve = useCallback((actionId: string) => decide(actionId, "approve"), [decide]);
  const reject = useCallback(
    (actionId: string, reason?: string) => decide(actionId, "reject", reason),
    [decide],
  );

  const reset = useCallback(() => {
    stopStream();
    generation.current += 1;
    pendingEvents.current = [];
    seqRef.current = 0;
    dispatch({ type: "reset" });
  }, [stopStream]);

  useEffect(
    () => () => {
      generation.current += 1;
      abortRef.current?.abort();
      if (flushTimer.current !== null) clearTimeout(flushTimer.current);
    },
    [],
  );

  return { state, start, cancel, approve, reject, reset };
}
