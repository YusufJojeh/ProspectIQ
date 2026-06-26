import { request } from "@/lib/api-client";
import type {
  CampaignActionResponse,
  CampaignCreateRequest,
  CampaignDetailResponse,
  CampaignGenerateDraftsResponse,
  CampaignLeadAddRequest,
  CampaignListResponse,
  CampaignUpdateRequest,
  SequenceStepResponse,
  SequenceStepUpdateRequest,
} from "@/types/api";

export function listCampaigns() {
  return request<CampaignListResponse>("/api/v1/campaigns");
}

export function createCampaign(payload: CampaignCreateRequest) {
  return request<CampaignDetailResponse>("/api/v1/campaigns", { method: "POST" }, payload);
}

export function getCampaign(campaignId: string) {
  return request<CampaignDetailResponse>(`/api/v1/campaigns/${campaignId}`);
}

export function updateCampaign(campaignId: string, payload: CampaignUpdateRequest) {
  return request<CampaignDetailResponse>(
    `/api/v1/campaigns/${campaignId}`,
    { method: "PATCH" },
    payload,
  );
}

export function archiveCampaign(campaignId: string) {
  return request<CampaignActionResponse>(`/api/v1/campaigns/${campaignId}`, {
    method: "DELETE",
  });
}

export function addCampaignLeads(campaignId: string, payload: CampaignLeadAddRequest) {
  return request<CampaignDetailResponse>(
    `/api/v1/campaigns/${campaignId}/leads`,
    { method: "POST" },
    payload,
  );
}

export function removeCampaignLead(campaignId: string, leadId: string) {
  return request<CampaignActionResponse>(
    `/api/v1/campaigns/${campaignId}/leads/${leadId}`,
    { method: "DELETE" },
  );
}

export function generateCampaignSequence(campaignId: string) {
  return request<SequenceStepResponse[]>(
    `/api/v1/campaigns/${campaignId}/generate-sequence`,
    { method: "POST" },
  );
}

export function updateCampaignSequenceStep(
  campaignId: string,
  stepId: string,
  payload: SequenceStepUpdateRequest,
) {
  return request<SequenceStepResponse>(
    `/api/v1/campaigns/${campaignId}/sequence-steps/${stepId}`,
    { method: "PATCH" },
    payload,
  );
}

export function generateCampaignDrafts(campaignId: string) {
  return request<CampaignGenerateDraftsResponse>(
    `/api/v1/campaigns/${campaignId}/generate-drafts`,
    { method: "POST" },
    {},
  );
}
