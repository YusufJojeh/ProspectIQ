import { request } from "@/lib/api-client";
import type {
  IcpProfileCreateRequest,
  IcpProfileListResponse,
  IcpProfileResponse,
  IcpProfileUpdateRequest,
  LeadIcpMatchListResponse,
  LeadIcpMatchResponse,
} from "@/types/api";

export function listIcpProfiles() {
  return request<IcpProfileListResponse>("/api/v1/icp-profiles");
}

export function createIcpProfile(payload: IcpProfileCreateRequest) {
  return request<IcpProfileResponse>(
    "/api/v1/icp-profiles",
    { method: "POST" },
    payload,
  );
}

export function updateIcpProfile(
  profileId: string,
  payload: IcpProfileUpdateRequest,
) {
  return request<IcpProfileResponse>(
    `/api/v1/icp-profiles/${profileId}`,
    { method: "PATCH" },
    payload,
  );
}

export function deleteIcpProfile(profileId: string) {
  return request<void>(`/api/v1/icp-profiles/${profileId}`, {
    method: "DELETE",
  });
}

export function recomputeIcpProfileMatch(profileId: string, leadId: string) {
  return request<LeadIcpMatchResponse>(
    `/api/v1/icp-profiles/${profileId}/match/${leadId}`,
    { method: "POST" },
  );
}

export function recomputeLeadIcpMatches(leadId: string) {
  return request<LeadIcpMatchListResponse>(
    `/api/v1/icp-profiles/leads/${leadId}/matches`,
    { method: "POST" },
  );
}
