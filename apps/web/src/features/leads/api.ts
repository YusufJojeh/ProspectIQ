import { request, requestBlob } from "@/lib/api-client";
import type {
  LeadActivityResponse,
  LeadNoteResponse,
  LeadEvidenceResponse,
  LeadListResponse,
  LeadResponse,
  LeadScoreBreakdownResponse,
  LeadScoreBand,
  LeadSortOption,
  LeadStatus,
} from "@/types/api";

type LeadListFilters = {
  page?: number;
  page_size?: number;
  q?: string;
  city?: string;
  category?: string;
  status?: LeadStatus | "all";
  band?: LeadScoreBand | "all";
  min_score?: number;
  max_score?: number;
  qualified?: boolean | "all";
  owner_user_id?: string | "all";
  search_job_id?: string | "all";
  has_website?: boolean | "all";
  sort?: LeadSortOption;
  lead_ids?: string[];
};

function buildLeadQuery(filters: LeadListFilters = {}) {
  const params = new URLSearchParams();
  if (filters.page) params.set("page", String(filters.page));
  if (filters.page_size) params.set("page_size", String(filters.page_size));
  if (filters.q) params.set("q", filters.q);
  if (filters.city) params.set("city", filters.city);
  if (filters.category) params.set("category", filters.category);
  if (filters.status && filters.status !== "all") params.set("status", filters.status);
  if (filters.band && filters.band !== "all") params.set("band", filters.band);
  if (filters.min_score !== undefined) params.set("min_score", String(filters.min_score));
  if (filters.max_score !== undefined) params.set("max_score", String(filters.max_score));
  if (filters.qualified !== undefined && filters.qualified !== "all") {
    params.set("qualified", String(filters.qualified));
  }
  if (filters.owner_user_id !== undefined && filters.owner_user_id !== "all") {
    params.set("owner_user_id", filters.owner_user_id);
  }
  if (filters.search_job_id && filters.search_job_id !== "all") params.set("search_job_id", filters.search_job_id);
  if (filters.has_website !== undefined && filters.has_website !== "all") {
    params.set("has_website", String(filters.has_website));
  }
  if (filters.sort) params.set("sort", filters.sort);
  for (const leadId of filters.lead_ids ?? []) {
    params.append("lead_ids", leadId);
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function listLeads(filters: LeadListFilters = {}) {
  return request<LeadListResponse>(`/api/v1/leads${buildLeadQuery(filters)}`);
}

export function getLead(leadId: string) {
  return request<LeadResponse>(`/api/v1/leads/${leadId}`);
}

export function refreshLead(leadId: string) {
  return request<LeadResponse>(`/api/v1/leads/${leadId}/refresh`, { method: "POST" });
}

export function getLeadEvidence(leadId: string) {
  return request<LeadEvidenceResponse>(`/api/v1/leads/${leadId}/evidence`);
}

export function getLeadScoreBreakdown(leadId: string) {
  return request<LeadScoreBreakdownResponse>(`/api/v1/leads/${leadId}/score-breakdown`);
}

export function listLeadActivity(leadId: string) {
  return request<LeadActivityResponse>(`/api/v1/leads/${leadId}/activity`);
}

export function addLeadNote(leadId: string, note: string) {
  return request<LeadNoteResponse>(`/api/v1/leads/${leadId}/notes`, { method: "POST" }, { note });
}

export function updateLeadStatus(leadId: string, status: LeadStatus, note?: string) {
  return request<LeadResponse>(`/api/v1/leads/${leadId}/status`, { method: "PATCH" }, { status, note });
}

export function assignLead(leadId: string, assignee_user_public_id: string | null) {
  return request<LeadResponse>(`/api/v1/leads/${leadId}/assign`, { method: "PATCH" }, { assignee_user_public_id });
}

export async function downloadLeadsExport(filters: LeadListFilters = {}) {
  const blob = await requestBlob(`/api/v1/exports/leads.csv${buildLeadQuery(filters)}`);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "prospectiq-leads.csv";
  anchor.click();
  URL.revokeObjectURL(url);
}
