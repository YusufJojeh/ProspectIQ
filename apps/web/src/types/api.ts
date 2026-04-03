export type UserRole = "admin" | "agency_manager" | "sales_user";
export type WebsitePreference = "any" | "must_have" | "must_be_missing";

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
  radius_km?: number;
  max_results: number;
  min_rating?: number;
  max_rating?: number;
  min_reviews?: number;
  max_reviews?: number;
  website_preference: WebsitePreference;
  keyword_filter?: string;
}

export interface SearchJobResponse {
  public_id: string;
  business_type: string;
  city: string;
  region: string | null;
  radius_km: number | null;
  max_results: number;
  min_rating: number | null;
  max_rating: number | null;
  min_reviews: number | null;
  max_reviews: number | null;
  website_preference: WebsitePreference;
  keyword_filter: string | null;
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
  provider_fetch_public_id: string;
  provider_status: string;
  request_mode: string;
  http_status: number | null;
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
  facts: Record<string, unknown>;
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

export interface LeadAnalysisResult {
  summary: string;
  weaknesses: string[];
  opportunities: string[];
  recommended_services: string[];
  outreach_subject: string;
  outreach_message: string;
  confidence: number;
}

export interface ServiceRecommendationResponse {
  public_id: string;
  service_name: string;
  rationale: string | null;
  confidence: number | null;
  rank_order: number;
  created_at: string;
}

export interface LeadAnalysisSnapshotResponse {
  public_id: string;
  lead_id: string;
  ai_provider: string;
  model_name: string;
  created_at: string;
  analysis: LeadAnalysisResult;
  service_recommendations: ServiceRecommendationResponse[];
}

export interface LatestLeadAnalysisResponse {
  lead_id: string;
  snapshot: LeadAnalysisSnapshotResponse | null;
}

export interface LeadAnalysisResponse {
  lead_id: string;
  analysis: LeadAnalysisResult;
}

export interface OutreachMessageResult {
  subject: string;
  message: string;
}

export interface OutreachDraftResponse {
  public_id: string;
  lead_id: string;
  ai_analysis_snapshot_public_id: string;
  subject: string;
  message: string;
  generated_subject: string;
  generated_message: string;
  has_manual_edits: boolean;
  created_at: string;
  updated_at: string;
}

export interface LatestOutreachResponse {
  lead_id: string;
  message: OutreachDraftResponse | null;
}

export interface OutreachMessageUpdateRequest {
  subject: string;
  message: string;
}

export interface LeadOutreachResponse {
  lead_id: string;
  message: OutreachMessageResult;
}

export interface LeadNoteCreateRequest {
  note: string;
}

export interface LeadNoteResponse {
  public_id: string;
  note: string;
  actor_user_public_id: string | null;
  actor_full_name: string | null;
  created_at: string;
}

export interface LeadActivityEntry {
  entry_id: string;
  entry_type: "status_change" | "note";
  actor_user_public_id: string | null;
  actor_full_name: string | null;
  created_at: string;
  from_status: LeadStatus | null;
  to_status: LeadStatus | null;
  note: string | null;
}

export interface LeadActivityResponse {
  lead_id: string;
  items: LeadActivityEntry[];
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

export interface ScoringConfigVersionListResponse {
  items: ScoringConfigVersionResponse[];
}

export interface ScoringConfigVersionCreateRequest {
  weights: ScoringWeights;
  thresholds: ScoringThresholds;
  note?: string;
}

export interface ProviderSettingsResponse {
  hl: string;
  gl: string;
  google_domain: string;
  enrich_top_n: number;
}

export interface ProviderSettingsUpdateRequest {
  hl?: string;
  gl?: string;
  google_domain?: string;
  enrich_top_n?: number;
}

export interface UserOption {
  public_id: string;
  email: string;
  full_name: string;
  role: UserRole;
}

export interface UserListResponse {
  items: UserOption[];
}

export interface AuditLogResponse {
  public_id: string;
  actor_user_public_id: string | null;
  event_name: string;
  details: string;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogResponse[];
}
