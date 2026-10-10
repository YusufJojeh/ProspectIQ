import { request } from "@/lib/api-client";
import type {
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
};

export function listProposalBrands() {
  return request<{ items: ProposalBrand[] }>(`${BASE}/brands`);
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
  brand_key: string;
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
