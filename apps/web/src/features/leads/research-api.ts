import { request } from "@/lib/api-client";
import type { EvidenceGraph, ResearchHistoryResponse } from "@/types/research";

export type ResearchDepth = "quick" | "standard" | "deep";

export interface LeadResearchResponse {
  lead_id: string;
  provider_fetch_id: string;
  provider: string;
  status: string;
  request_id: string | null;
  message: string;
  depth: ResearchDepth;
  mode: "planned" | "agentic";
  providers_used: string[];
  contradictions_detected: number;
  tool_calls_made: number;
}

export function getLeadEvidenceGraph(leadId: string) {
  return request<EvidenceGraph>(`/api/v1/leads/${leadId}/evidence-graph`);
}

export function getLeadResearchHistory(
  leadId: string,
  page = 1,
  perPage = 10,
) {
  return request<ResearchHistoryResponse>(
    `/api/v1/leads/${leadId}/research-history?page=${page}&per_page=${perPage}`,
  );
}

export function runLeadResearch(leadId: string, depth: ResearchDepth) {
  return request<LeadResearchResponse>(
    `/api/v1/leads/${leadId}/research`,
    { method: "POST" },
    { depth, mode: "planned" },
  );
}
