import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useJobStream } from "./use-job-stream";

function sse(stage: string, progress: number, message = stage): string {
  return `data: ${JSON.stringify({ stage, progress, message })}\r\n\r\n`;
}

function streamResponse(body: string): Response {
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("useJobStream", () => {
  it("applies live progress and stops once the job is done", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        streamResponse(`: keepalive\n\n${sse("scoring", 80)}${sse("done", 100, "complete")}`),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useJobStream("job_1"), { wrapper });

    await waitFor(() => expect(result.current.isDone).toBe(true));
    expect(result.current.progress).toBe(100);
    expect(result.current.message).toBe("complete");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("reconnects when the server closes the stream without a terminal event", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(streamResponse(sse("fetching", 20)))
      .mockResolvedValueOnce(streamResponse(sse("done", 100)));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useJobStream("job_1"), { wrapper });

    await waitFor(() => expect(result.current.stage).toBe("fetching"));
    await waitFor(() => expect(result.current.isDone).toBe(true), { timeout: 3_000 });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("offers a manual reconnect after the retry budget is spent", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 503 }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useJobStream("job_1"), { wrapper });

    for (let i = 0; i < 4; i += 1) {
      await vi.advanceTimersByTimeAsync(4_000);
    }
    await waitFor(() => expect(result.current.canReconnect).toBe(true));
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("does not connect without a job id", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderHook(() => useJobStream(null), { wrapper });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
