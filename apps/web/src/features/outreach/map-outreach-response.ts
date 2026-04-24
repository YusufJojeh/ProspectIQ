import type { OutreachDraftResponse, OutreachMessageResult } from "@/types/api";

/** Map persisted outreach draft API shape to compact preview (same fields as legacy /leads/.../outreach/generate). */
export function outreachDraftToMessagePreview(draft: OutreachDraftResponse): OutreachMessageResult {
  return {
    subject: draft.subject,
    message: draft.message,
    tone: draft.tone,
  };
}
