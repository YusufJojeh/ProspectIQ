import { request } from "@/lib/api-client";
import type { ActiveScoringConfigResponse, ProviderSettingsResponse } from "@/types/api";

export function getActiveScoringConfig() {
  return request<ActiveScoringConfigResponse>("/api/v1/admin/scoring-config/active");
}

export function getProviderSettings() {
  return request<ProviderSettingsResponse>("/api/v1/admin/provider-settings");
}
