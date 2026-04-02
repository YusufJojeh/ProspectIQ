import { request } from "@/lib/api-client";
import type {
  LeadEvidenceResponse,
  LeadListResponse,
  LeadResponse,
  LeadScoreBreakdownResponse,
} from "@/types/api";

export function listLeads() {
  return request<LeadListResponse>("/api/v1/leads");
}

export function getLead(leadId: string) {
  return request<LeadResponse>(`/api/v1/leads/${leadId}`);
}

export function getLeadEvidence(leadId: string) {
  return request<LeadEvidenceResponse>(`/api/v1/leads/${leadId}/evidence`);
}

export function getLeadScoreBreakdown(leadId: string) {
  return request<LeadScoreBreakdownResponse>(`/api/v1/leads/${leadId}/score-breakdown`);
}
