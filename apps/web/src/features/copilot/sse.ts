import type { AgentEvent } from "@/types/agent";

export interface SseFrame {
  id: string | null;
  event: string;
  data: string;
}

/**
 * Incremental Server-Sent-Events parser. Feed decoded text chunks; complete
 * frames (terminated by a blank line) are returned and any partial tail is
 * retained for the next chunk. Handles CRLF, multi-line `data:` and comments.
 */
export class SseParser {
  private buffer = "";

  push(chunk: string): SseFrame[] {
    this.buffer += chunk.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    const frames: SseFrame[] = [];
    let boundary = this.buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const raw = this.buffer.slice(0, boundary);
      this.buffer = this.buffer.slice(boundary + 2);
      const frame = parseFrame(raw);
      if (frame) frames.push(frame);
      boundary = this.buffer.indexOf("\n\n");
    }
    return frames;
  }
}

function parseFrame(raw: string): SseFrame | null {
  let id: string | null = null;
  let event = "message";
  const data: string[] = [];
  for (const line of raw.split("\n")) {
    if (line === "" || line.startsWith(":")) continue;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "id") id = value;
    else if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  if (data.length === 0) return null;
  return { id, event, data: data.join("\n") };
}

/** Parses a frame's JSON into an AgentEvent, or null if it is malformed. */
export function frameToEvent(frame: SseFrame): AgentEvent | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(frame.data);
  } catch {
    return null;
  }
  if (typeof parsed !== "object" || parsed === null) return null;
  const record = parsed as Record<string, unknown>;
  const seq = record.seq;
  const eventType = record.event_type;
  if (typeof seq !== "number" || typeof eventType !== "string") return null;
  const payload =
    typeof record.payload === "object" && record.payload !== null
      ? (record.payload as Record<string, unknown>)
      : {};
  return {
    event_id: typeof record.event_id === "string" ? record.event_id : `seq-${seq}`,
    seq,
    event_type: eventType,
    payload,
    created_at: typeof record.created_at === "string" ? record.created_at : "",
  };
}

/** Exponential back-off with a cap; `attempt` starts at 0. */
export function backoffDelayMs(attempt: number, baseMs = 500, capMs = 15_000): number {
  return Math.min(capMs, baseMs * 2 ** attempt);
}
