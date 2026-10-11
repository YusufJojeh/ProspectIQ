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

export type BrandMarkShape = "square" | "hex" | "circle";
export type BrandFontStyle = "sans" | "serif";

export interface BrandMilestone {
  title: string;
  description: string;
}

/** Everything a workspace controls about how its proposals look and start. */
export interface BrandFields {
  name: string;
  tagline: string;
  mark: string;
  mark_shape: BrandMarkShape;
  font_style: BrandFontStyle;
  /** PNG/JPEG/WebP data URL; replaces the mark when set. */
  logo_data_url: string | null;
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
  default_outcome: string;
  default_commercial_notes: string;
  default_validity_notes: string;
  default_milestones: BrandMilestone[];
}

/** One of the workspace's own proposal brands. */
export interface ProposalBrand extends BrandFields {
  public_id: string;
  is_default: boolean;
  archived: boolean;
}

/** A starting point for a new brand (the reference kits and a neutral style). */
export interface BrandTemplate {
  key: string;
  values: BrandFields;
}

export interface BrandCreateRequest extends BrandFields {
  is_default?: boolean;
}

export type BrandUpdateRequest = Partial<BrandFields> & { archived?: boolean };

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
  brand_id: string;
  brand_name: string;
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
  brand_id?: string;
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

export type AuditFindingKey = "website" | "rating" | "reviews" | "phone" | "email" | "social";
export type AuditFindingStatus = "good" | "improve" | "missing";

export interface AuditFinding {
  key: AuditFindingKey;
  status: AuditFindingStatus;
  /** Numbers the sentence quotes, e.g. rating and peer_median. */
  values: Record<string, number>;
}

export interface AuditBenchmark {
  peer_count: number;
  median_rating: number | null;
  median_reviews: number;
  website_pct: number;
}

export interface AuditEvidence {
  signal_type: string;
  text: string;
  source_url: string | null;
}

export interface LeadAudit {
  lead_id: string;
  company_name: string;
  category: string | null;
  city: string | null;
  website_url: string | null;
  email: string | null;
  generated_on: string;
  findings: AuditFinding[];
  benchmark: AuditBenchmark | null;
  evidence: AuditEvidence[];
}
