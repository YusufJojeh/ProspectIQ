import { request } from "@/lib/api-client";
import type {
  BrandCreateRequest,
  BrandTemplate,
  BrandUpdateRequest,
  LeadAudit,
  Proposal,
  ProposalBrand,
  ProposalDecision,
  ProposalLanguage,
  ProposalSummary,
  ProposalUpdateRequest,
} from "@/types/proposals";

const BASE = "/api/v1/proposals";

export const proposalKeys = {
  all: ["proposals"] as const,
  list: (leadId: string | null) => ["proposals", "list", leadId ?? "all"] as const,
  detail: (proposalId: string) => ["proposals", "detail", proposalId] as const,
  brands: ["proposals", "brands"] as const,
  brandList: (includeArchived: boolean) => ["proposals", "brands", "list", includeArchived] as const,
  brand: (brandId: string) => ["proposals", "brands", "detail", brandId] as const,
  brandTemplates: ["proposals", "brand-templates"] as const,
  audit: (leadId: string) => ["proposals", "lead-audit", leadId] as const,
};

export function listProposalBrands(includeArchived = false) {
  const query = includeArchived ? "?include_archived=true" : "";
  return request<{ items: ProposalBrand[] }>(`${BASE}/brands${query}`);
}

export function listBrandTemplates() {
  return request<{ items: BrandTemplate[] }>(`${BASE}/brand-templates`);
}

export function getProposalBrand(brandId: string) {
  return request<ProposalBrand>(`${BASE}/brands/${brandId}`);
}

export function createProposalBrand(payload: BrandCreateRequest) {
  return request<ProposalBrand>(`${BASE}/brands`, { method: "POST" }, payload);
}

export function updateProposalBrand(brandId: string, payload: BrandUpdateRequest) {
  return request<ProposalBrand>(`${BASE}/brands/${brandId}`, { method: "PATCH" }, payload);
}

export function setDefaultProposalBrand(brandId: string) {
  return request<ProposalBrand>(`${BASE}/brands/${brandId}/default`, { method: "POST" });
}

export function listProposals(leadId?: string | null) {
  const query = leadId ? `?lead_id=${encodeURIComponent(leadId)}` : "";
  return request<{ items: ProposalSummary[] }>(`${BASE}${query}`);
}

export function getProposal(proposalId: string) {
  return request<Proposal>(`${BASE}/${proposalId}`);
}

export function createProposal(payload: {
  lead_id: string;
  brand_id?: string;
  language?: ProposalLanguage;
}) {
  return request<Proposal>(BASE, { method: "POST" }, payload);
}

export function updateProposal(proposalId: string, payload: ProposalUpdateRequest) {
  return request<Proposal>(`${BASE}/${proposalId}`, { method: "PATCH" }, payload);
}

export function markProposalReady(proposalId: string) {
  return request<Proposal>(`${BASE}/${proposalId}/ready`, { method: "POST" });
}

export function markProposalSent(proposalId: string) {
  return request<Proposal>(`${BASE}/${proposalId}/sent`, { method: "POST" });
}

export function recordProposalDecision(proposalId: string, decision: ProposalDecision) {
  return request<Proposal>(`${BASE}/${proposalId}/decision`, { method: "POST" }, { decision });
}

export function getLeadAudit(leadId: string) {
  return request<LeadAudit>(`${BASE}/lead-audit/${encodeURIComponent(leadId)}`);
}
