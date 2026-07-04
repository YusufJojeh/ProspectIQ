import { request } from "@/lib/api-client";
import type {
  AIFeedbackRequest,
  AIFeedbackResponse,
  LatestLeadAnalysisResponse,
  LeadAiEvidenceResponse,
  LeadAnalysisSnapshotResponse,
} from "@/types/api";

export function getLatestLeadAnalysis(leadId: string) {
  return request<LatestLeadAnalysisResponse>(
    `/api/v1/ai-analysis/leads/${leadId}/latest`,
  );
}

export function generateLeadAnalysis(leadId: string) {
  return request<LeadAnalysisSnapshotResponse>(
    `/api/v1/ai-analysis/leads/${leadId}/generate`,
    {
      method: "POST",
    },
  );
}

export function getLeadAiEvidence(leadId: string) {
  return request<LeadAiEvidenceResponse>(
    `/api/v1/leads/${leadId}/ai-evidence`,
  );
}

export function submitAnalysisFeedback(
  snapshotId: string,
  payload: AIFeedbackRequest,
) {
  return request<AIFeedbackResponse>(
    `/api/v1/ai-analysis/${snapshotId}/feedback`,
    { method: "POST" },
    payload,
  );
}
