import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { SseParser } from "@/features/copilot/sse";
import { buildRequestUrl, readToken } from "@/lib/api-client";

export type JobStreamStage =
  | "fetching"
  | "normalizing"
  | "enriching"
  | "scoring"
  | "done"
  | "error";

export type JobStreamState = {
  stage: JobStreamStage | null;
  progress: number;
  message: string;
  isDone: boolean;
  isError: boolean;
  canReconnect: boolean;
};

type RawEvent = {
  stage: JobStreamStage;
  progress: number;
  message: string;
};

const BACKOFF_DELAYS_MS = [1_000, 2_000, 4_000];

const INITIAL_STATE: JobStreamState = {
  stage: null,
  progress: 0,
  message: "",
  isDone: false,
  isError: false,
  canReconnect: false,
};

export function useJobStream(jobId: string | null): JobStreamState & { reconnect: () => void } {
  const queryClient = useQueryClient();
  const [state, setState] = useState<JobStreamState>(INITIAL_STATE);
  const attemptRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const stoppedRef = useRef(false);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function clearRetryTimer() {
    if (retryTimerRef.current !== null) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
  }

  /** Retries with back-off; returns false once the budget is spent. */
  function scheduleReconnect(): boolean {
    const attempt = attemptRef.current;
    if (attempt >= BACKOFF_DELAYS_MS.length) return false;
    attemptRef.current += 1;
    clearRetryTimer();
    retryTimerRef.current = setTimeout(connect, BACKOFF_DELAYS_MS[attempt]);
    return true;
  }

  function start() {
    if (!jobId) return;

    clearRetryTimer();
    stoppedRef.current = false;
    attemptRef.current = 0;
    setState(INITIAL_STATE);
    connect();
  }

  function connect() {
    retryTimerRef.current = null;
    if (stoppedRef.current || !jobId) return;

    const token = readToken();
    const controller = new AbortController();
    abortRef.current = controller;

    const url = buildRequestUrl(`/api/v1/search-jobs/${jobId}/stream`);

    void (async () => {
      try {
        const response = await fetch(url, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        const parser = new SseParser();

        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;

          for (const frame of parser.push(decoder.decode(value, { stream: true }))) {
            let parsed: RawEvent;
            try {
              parsed = JSON.parse(frame.data) as RawEvent;
            } catch {
              continue; // skip malformed event
            }
            attemptRef.current = 0; // real progress arrived — reset back-off
            const isDone = parsed.stage === "done";
            const isError = parsed.stage === "error";
            setState({
              stage: parsed.stage,
              progress: parsed.progress,
              message: parsed.message,
              isDone,
              isError,
              canReconnect: false,
            });
            if (isDone || isError) {
              void queryClient.invalidateQueries({ queryKey: ["search-jobs"] });
              void queryClient.invalidateQueries({ queryKey: ["leads"] });
              controller.abort();
              return;
            }
          }
        }

        // The server closed without a terminal event (idle deadline or no live
        // transport): the job may still be running, so keep listening.
        if (!stoppedRef.current && !scheduleReconnect()) {
          setState((prev) => ({ ...prev, canReconnect: true }));
        }
      } catch (err) {
        if (stoppedRef.current) return;
        if (err instanceof DOMException && err.name === "AbortError") return;

        if (!scheduleReconnect()) {
          setState((prev) => ({ ...prev, canReconnect: true }));
        }
      }
    })();
  }

  useEffect(() => {
    if (!jobId) return;
    start();
    return () => {
      stoppedRef.current = true;
      clearRetryTimer();
      abortRef.current?.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  return {
    ...state,
    reconnect: () => {
      abortRef.current?.abort();
      start();
    },
  };
}
