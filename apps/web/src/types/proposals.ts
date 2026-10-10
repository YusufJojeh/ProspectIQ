export type ProposalStatus = "draft" | "ready" | "sent" | "accepted" | "declined";
export type ProposalLanguage = "en" | "ar";
export type ProposalDecision = "accepted" | "declined";

export type ProposalIssue =
  | "missing_title"
  | "missing_client_company"
  | "missing_client_email"
  | "invalid_client_email"
  | "missing_outcome"
  | "no_milestones"
  | "milestone_missing_title"
  | "milestone_missing_amount"
  | "invalid_validity"
  | "expired"
  | "placeholder_text";

export interface ProposalBrand {
  key: string;
  name: string;
  tagline: string;
  mark: string;
  /** "square" (Yusuf Jojeh kit) or "hex" (HexaTerminal kit). */
  mark_shape: string;
  number_prefix: string;
  signer_label: string;
  client_signer_label: string;
  footer_contact: string;
  paper: string;
  ink: string;
  muted: string;
  line: string;
  accent: string;
  accent_secondary: string;
  background: string;
  radius_px: number;
  default_currency: string;
  validity_days: number;
}

export interface ProposalMilestone {
  title: string;
  description: string;
  /** Minor units (cents); null while unpriced. */
  amount_minor: number | null;
  share_pct: number | null;
}

export interface ProposalTotals {
  total_minor: number;
  deposit_minor: number;
  remaining_minor: number;
}

export interface Proposal {
  public_id: string;
  number: string;
  status: ProposalStatus;
  lead_id: string;
  lead_company_name: string;
  brand: ProposalBrand;
  language: ProposalLanguage;
  title: string;
  client_company: string;
  client_contact_name: string | null;
  client_email: string | null;
  client_location: string | null;
  currency: string;
  issue_date: string;
  valid_until: string;
  outcome: string;
  milestones: ProposalMilestone[];
  commercial_notes: string;
  validity_notes: string;
  sender_contact: string;
  pricing_basis: string | null;
  source_agent_run_id: string | null;
  totals: ProposalTotals;
  readiness: { ready: boolean; issues: ProposalIssue[] };
  sent_at: string | null;
  decided_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProposalSummary {
  public_id: string;
  number: string;
  status: ProposalStatus;
  lead_id: string;
  lead_company_name: string;
  brand_key: string;
  title: string;
  client_company: string;
  currency: string;
  total_minor: number;
  valid_until: string;
  ready: boolean;
  updated_at: string;
}

export interface ProposalMilestoneInput {
  title: string;
  description: string;
  amount_minor: number | null;
}

export interface ProposalUpdateRequest {
  brand_key?: string;
  language?: ProposalLanguage;
  title?: string;
  client_company?: string;
  client_contact_name?: string | null;
  client_email?: string | null;
  client_location?: string | null;
  currency?: string;
  issue_date?: string;
  valid_until?: string;
  outcome?: string;
  milestones?: ProposalMilestoneInput[];
  commercial_notes?: string;
  validity_notes?: string;
  sender_contact?: string;
}
