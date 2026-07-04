import { request } from "@/lib/api-client";
import type {
  CampaignCreateDealsResponse,
  CrmActivityCreateRequest,
  CrmActivityResponse,
  CrmActivityUpdateRequest,
  CrmDealActionResponse,
  CrmDealCreateRequest,
  CrmDealDetailResponse,
  CrmDealListResponse,
  CrmDealResponse,
  CrmDealUpdateRequest,
  CrmPipelineListResponse,
  CrmPipelineResponse,
  DealStatus,
} from "@/types/api";

type DealFilters = {
  pipeline_id?: string;
  stage_id?: string;
  lead_id?: string;
  campaign_id?: string;
  status?: DealStatus;
};

function buildDealQuery(filters: DealFilters = {}) {
  const params = new URLSearchParams();
  if (filters.pipeline_id) params.set("pipeline_id", filters.pipeline_id);
  if (filters.stage_id) params.set("stage_id", filters.stage_id);
  if (filters.lead_id) params.set("lead_id", filters.lead_id);
  if (filters.campaign_id) params.set("campaign_id", filters.campaign_id);
  if (filters.status) params.set("status", filters.status);
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function listCrmPipelines() {
  return request<CrmPipelineListResponse>("/api/v1/crm/pipelines");
}

export function getCrmPipeline(pipelineId: string) {
  return request<CrmPipelineResponse>(`/api/v1/crm/pipelines/${pipelineId}`);
}

export function listCrmDeals(filters: DealFilters = {}) {
  return request<CrmDealListResponse>(`/api/v1/crm/deals${buildDealQuery(filters)}`);
}

export function createCrmDeal(payload: CrmDealCreateRequest) {
  return request<CrmDealResponse>("/api/v1/crm/deals", { method: "POST" }, payload);
}

export function getCrmDeal(dealId: string) {
  return request<CrmDealDetailResponse>(`/api/v1/crm/deals/${dealId}`);
}

export function updateCrmDeal(dealId: string, payload: CrmDealUpdateRequest) {
  return request<CrmDealResponse>(`/api/v1/crm/deals/${dealId}`, { method: "PATCH" }, payload);
}

export function archiveCrmDeal(dealId: string) {
  return request<CrmDealActionResponse>(`/api/v1/crm/deals/${dealId}`, { method: "DELETE" });
}

export function moveCrmDeal(dealId: string, stageId: string) {
  return request<CrmDealResponse>(
    `/api/v1/crm/deals/${dealId}/move`,
    { method: "POST" },
    { stage_id: stageId },
  );
}

export function markCrmDealWon(dealId: string) {
  return request<CrmDealResponse>(`/api/v1/crm/deals/${dealId}/mark-won`, {
    method: "POST",
  });
}

export function markCrmDealLost(dealId: string, lostReason?: string) {
  return request<CrmDealResponse>(
    `/api/v1/crm/deals/${dealId}/mark-lost`,
    { method: "POST" },
    { lost_reason: lostReason ?? null },
  );
}

export function createCrmActivity(dealId: string, payload: CrmActivityCreateRequest) {
  return request<CrmActivityResponse>(
    `/api/v1/crm/deals/${dealId}/activities`,
    { method: "POST" },
    payload,
  );
}

export function updateCrmActivity(
  dealId: string,
  activityId: string,
  payload: CrmActivityUpdateRequest,
) {
  return request<CrmActivityResponse>(
    `/api/v1/crm/deals/${dealId}/activities/${activityId}`,
    { method: "PATCH" },
    payload,
  );
}

export function completeCrmActivity(dealId: string, activityId: string) {
  return request<CrmActivityResponse>(
    `/api/v1/crm/deals/${dealId}/activities/${activityId}/complete`,
    { method: "POST" },
  );
}

export function createLeadDeal(leadId: string, allowDuplicateOpen = false) {
  return request<CrmDealResponse>(
    `/api/v1/leads/${leadId}/create-deal`,
    { method: "POST" },
    { allow_duplicate_open: allowDuplicateOpen },
  );
}

export function createCampaignDeals(campaignId: string, allowDuplicateOpen = false) {
  return request<CampaignCreateDealsResponse>(
    `/api/v1/campaigns/${campaignId}/create-deals`,
    { method: "POST" },
    { allow_duplicate_open: allowDuplicateOpen },
  );
}
