import { request } from "@/lib/api-client";
import type {
  ActiveScoringConfigResponse,
  AuditLogListResponse,
  OperationalHealthResponse,
  PromptTemplateCreateRequest,
  PromptTemplateListResponse,
  PromptTemplateResponse,
  ProviderSettingsResponse,
  ProviderSettingsUpdateRequest,
  ScoringConfigVersionResponse,
  ScoringConfigVersionCreateRequest,
  ScoringConfigVersionListResponse,
  WorkspaceSettingsResponse,
  WorkspaceSettingsUpdateRequest,
} from "@/types/api";

export function getActiveScoringConfig() {
  return request<ActiveScoringConfigResponse>("/api/v1/admin/scoring-config/active");
}

export function listScoringVersions() {
  return request<ScoringConfigVersionListResponse>("/api/v1/admin/scoring-config/versions");
}

export function createScoringVersion(payload: ScoringConfigVersionCreateRequest) {
  return request<ScoringConfigVersionResponse>("/api/v1/admin/scoring-config/versions", { method: "POST" }, payload);
}

export function activateScoringVersion(versionId: string) {
  return request<ActiveScoringConfigResponse>(`/api/v1/admin/scoring-config/activate/${versionId}`, { method: "POST" });
}

export function getProviderSettings() {
  return request<ProviderSettingsResponse>("/api/v1/admin/provider-settings");
}

export function updateProviderSettings(payload: ProviderSettingsUpdateRequest) {
  return request<ProviderSettingsResponse>("/api/v1/admin/provider-settings", { method: "PATCH" }, payload);
}

export function listPromptTemplates() {
  return request<PromptTemplateListResponse>("/api/v1/admin/prompt-templates");
}

export function createPromptTemplate(payload: PromptTemplateCreateRequest) {
  return request<PromptTemplateResponse>("/api/v1/admin/prompt-templates", { method: "POST" }, payload);
}

export function activatePromptTemplate(promptTemplateId: string) {
  return request<PromptTemplateResponse>(`/api/v1/admin/prompt-templates/activate/${promptTemplateId}`, {
    method: "POST",
  });
}

export function getOperationalHealth() {
  return request<OperationalHealthResponse>("/api/v1/admin/operations/health");
}

export function listAuditLogs() {
  return request<AuditLogListResponse>("/api/v1/audit-logs");
}

export function getWorkspaceSettings() {
  return request<WorkspaceSettingsResponse>("/api/v1/workspace-settings");
}

export function updateWorkspaceSettings(payload: WorkspaceSettingsUpdateRequest) {
  return request<WorkspaceSettingsResponse>("/api/v1/workspace-settings", { method: "PATCH" }, payload);
}
