export type UserRole = "admin" | "manager" | "sales";

export type SearchJobStatus =
  | "queued"
  | "running"
  | "completed"
  | "partially_completed"
  | "failed";

export type LeadStatus =
  | "new"
  | "reviewed"
  | "qualified"
  | "contacted"
  | "interested"
  | "won"
  | "lost"
  | "archived";

export type LeadScoreBand = "high" | "medium" | "low" | "not_qualified";

export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
}

export interface AuthenticatedUser {
  public_id: string;
  workspace_public_id: string;
  email: string;
  full_name: string;
  role: UserRole;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthenticatedUser;
}

export interface LoginRequest {
  workspace: string;
  email: string;
  password: string;
}

export interface SearchJobCreateRequest {
  business_type: string;
  city: string;
  region?: string;
  max_results: number;
  min_rating?: number;
  min_reviews?: number;
  require_website: boolean;
}

export interface SearchJobResponse {
  public_id: string;
  business_type: string;
  city: string;
  region: string | null;
  max_results: number;
  min_rating: number | null;
  min_reviews: number | null;
  require_website: boolean;
  status: SearchJobStatus;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
  candidates_found: number;
  leads_upserted: number;
  enriched_count: number;
  provider_error_count: number;
}

export interface SearchJobListResponse {
  items: SearchJobResponse[];
}

export interface LeadResponse {
  public_id: string;
  company_name: string;
  category: string | null;
  address: string | null;
  city: string | null;
  phone: string | null;
  website_url: string | null;
  website_domain: string | null;
  review_count: number;
  rating: number | null;
  lat: number | null;
  lng: number | null;
  data_completeness: number;
  data_confidence: number;
  has_website: boolean;
  status: LeadStatus;
  assigned_to_user_public_id: string | null;
  latest_score: number | null;
  latest_band: LeadScoreBand | null;
  created_at: string;
  updated_at: string;
}

export interface LeadListResponse {
  items: LeadResponse[];
  pagination: PaginationMeta;
}

export interface LeadEvidenceItem {
  source_type: string;
  data_cid: string | null;
  data_id: string | null;
  place_id: string | null;
  company_name: string;
  category: string | null;
  address: string | null;
  city: string | null;
  phone: string | null;
  website_url: string | null;
  website_domain: string | null;
  rating: number | null;
  review_count: number;
  lat: number | null;
  lng: number | null;
  confidence: number;
  completeness: number;
  created_at: string;
}

export interface LeadEvidenceResponse {
  lead_id: string;
  items: LeadEvidenceItem[];
}

export interface ScoreBreakdownItem {
  key: string;
  label: string;
  weight: number;
  contribution: number;
  reason: string;
}

export interface LeadScoreBreakdownResponse {
  lead_id: string;
  scoring_version_id: string;
  total_score: number;
  band: LeadScoreBand;
  qualified: boolean;
  breakdown: ScoreBreakdownItem[];
}

export interface ScoringWeights {
  local_trust: number;
  website_presence: number;
  search_visibility: number;
  opportunity: number;
  data_confidence: number;
}

export interface ScoringThresholds {
  high_min: number;
  medium_min: number;
  low_min: number;
  confidence_min: number;
}

export interface ScoringConfigVersionResponse {
  public_id: string;
  weights: ScoringWeights;
  thresholds: ScoringThresholds;
  note: string | null;
  created_at: string;
  created_by_user_public_id: string;
}

export interface ActiveScoringConfigResponse {
  active_version: ScoringConfigVersionResponse;
}

export interface ProviderSettingsResponse {
  hl: string;
  gl: string;
  google_domain: string;
  enrich_top_n: number;
}
