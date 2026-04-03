import { request } from "@/lib/api-client";
import type {
  LatestLeadAnalysisResponse,
  LeadAnalysisSnapshotResponse,
} from "@/types/api";

export function getLatestLeadAnalysis(leadId: string) {
  return request<LatestLeadAnalysisResponse>(`/api/v1/ai-analysis/leads/${leadId}/latest`);
}

export function generateLeadAnalysis(leadId: string) {
  return request<LeadAnalysisSnapshotResponse>(`/api/v1/ai-analysis/leads/${leadId}/generate`, {
    method: "POST",
  });
}
