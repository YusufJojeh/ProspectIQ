import { request } from "@/lib/api-client";
import type {
  AdminAIUsageResponse,
  AdminActionResponse,
  AdminFeatureHealthResponse,
  AdminInvoiceListResponse,
  AdminPlanListResponse,
  AdminProvidersResponse,
  AdminSearchJobListResponse,
  AdminSubscriptionListResponse,
  AdminUsageListResponse,
  AdminUserListResponse,
  AdminWorkspaceDetailResponse,
  AdminWorkspaceListResponse,
  PlatformAdminOverviewResponse,
} from "@/types/api";

export function getPlatformOverview() {
  return request<PlatformAdminOverviewResponse>("/api/v1/admin/overview");
}

export function listPlatformWorkspaces() {
  return request<AdminWorkspaceListResponse>("/api/v1/admin/workspaces");
}

export function getPlatformWorkspace(workspaceId: string) {
  return request<AdminWorkspaceDetailResponse>(
    `/api/v1/admin/workspaces/${workspaceId}`,
  );
}

export function enablePlatformWorkspace(workspaceId: string) {
  return request<AdminActionResponse>(
    `/api/v1/admin/workspaces/${workspaceId}/enable`,
    { method: "POST" },
  );
}

export function disablePlatformWorkspace(workspaceId: string) {
  return request<AdminActionResponse>(
    `/api/v1/admin/workspaces/${workspaceId}/disable`,
    { method: "POST" },
  );
}

export function listPlatformUsers() {
  return request<AdminUserListResponse>("/api/v1/admin/users");
}

export function enablePlatformUser(userId: string) {
  return request<AdminActionResponse>(`/api/v1/admin/users/${userId}/enable`, {
    method: "POST",
  });
}

export function disablePlatformUser(userId: string) {
  return request<AdminActionResponse>(`/api/v1/admin/users/${userId}/disable`, {
    method: "POST",
  });
}

export function listPlatformPlans() {
  return request<AdminPlanListResponse>("/api/v1/admin/plans");
}

export function listPlatformSubscriptions() {
  return request<AdminSubscriptionListResponse>("/api/v1/admin/subscriptions");
}

export function listPlatformInvoices() {
  return request<AdminInvoiceListResponse>("/api/v1/admin/invoices");
}

export function listPlatformUsage() {
  return request<AdminUsageListResponse>("/api/v1/admin/usage");
}

export function getPlatformProviders() {
  return request<AdminProvidersResponse>("/api/v1/admin/providers");
}

export function listPlatformSearchJobs() {
  return request<AdminSearchJobListResponse>("/api/v1/admin/search-jobs");
}

export function getPlatformAiUsage() {
  return request<AdminAIUsageResponse>("/api/v1/admin/ai-usage");
}

export function getPlatformFeatureHealth() {
  return request<AdminFeatureHealthResponse>("/api/v1/admin/feature-health");
}
