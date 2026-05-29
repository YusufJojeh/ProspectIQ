import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { buildRequestUrl, readToken } from "@/lib/api-client";

export type JobStreamStage = "fetching" | "normalizing" | "scoring" | "done" | "error";

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

  function start() {
    if (!jobId) return;

    stoppedRef.current = false;
    attemptRef.current = 0;
    setState(INITIAL_STATE);
    connect();
  }

  function connect() {
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

        attemptRef.current = 0; // connection succeeded — reset backoff

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const chunks = buffer.split("\n\n");
          buffer = chunks.pop() ?? "";

          for (const chunk of chunks) {
            const dataLine = chunk.split("\n").find((l) => l.startsWith("data: "));
            if (!dataLine) continue;
            try {
              const parsed = JSON.parse(dataLine.slice(6)) as RawEvent;
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
                return;
              }
            } catch {
              // skip malformed event
            }
          }
        }
      } catch (err) {
        if (stoppedRef.current) return;
        if (err instanceof DOMException && err.name === "AbortError") return;

        const attempt = attemptRef.current;
        if (attempt < BACKOFF_DELAYS_MS.length) {
          attemptRef.current += 1;
          setTimeout(connect, BACKOFF_DELAYS_MS[attempt]);
        } else {
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
