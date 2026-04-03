import { request } from "@/lib/api-client";
import type {
  LatestOutreachResponse,
  OutreachDraftResponse,
  OutreachMessageUpdateRequest,
} from "@/types/api";

export function getLatestOutreach(leadId: string) {
  return request<LatestOutreachResponse>(`/api/v1/outreach/leads/${leadId}/latest`);
}

export function generateLeadOutreach(leadId: string) {
  return request<OutreachDraftResponse>(`/api/v1/outreach/leads/${leadId}/generate`, {
    method: "POST",
  });
}

export function updateOutreachDraft(
  messageId: string,
  payload: OutreachMessageUpdateRequest,
) {
  return request<OutreachDraftResponse>(`/api/v1/outreach/messages/${messageId}`, {
    method: "PATCH",
  }, payload);
}
