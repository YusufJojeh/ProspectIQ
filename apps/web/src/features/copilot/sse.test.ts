import { describe, expect, it } from "vitest";

import { SseParser, backoffDelayMs, frameToEvent } from "./sse";

describe("SseParser", () => {
  it("reassembles frames split across chunks and handles CRLF", () => {
    const parser = new SseParser();
    expect(parser.push("id: 1\r\nevent: agent_star")).toEqual([]);
    const frames = parser.push('ted\r\ndata: {"seq":1}\r\n\r\n: comment\n\n');
    expect(frames).toEqual([{ id: "1", event: "agent_started", data: '{"seq":1}' }]);
  });

  it("joins multi-line data and skips data-less frames", () => {
    const frames = new SseParser().push("data: a\ndata: b\n\nevent: x\n\n");
    expect(frames).toEqual([{ id: null, event: "message", data: "a\nb" }]);
  });
});

describe("frameToEvent", () => {
  it("rejects malformed payloads instead of throwing", () => {
    expect(frameToEvent({ id: null, event: "x", data: "{" })).toBeNull();
    expect(frameToEvent({ id: null, event: "x", data: '{"seq":"1"}' })).toBeNull();
    const ok = frameToEvent({
      id: "3",
      event: "x",
      data: '{"seq":3,"event_type":"agent_started","payload":null}',
    });
    expect(ok?.seq).toBe(3);
    expect(ok?.payload).toEqual({});
  });
});

describe("backoffDelayMs", () => {
  it("grows exponentially up to the cap", () => {
    expect([0, 1, 2, 10].map((n) => backoffDelayMs(n))).toEqual([500, 1000, 2000, 15000]);
  });
});
