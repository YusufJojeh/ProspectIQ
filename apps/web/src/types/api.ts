export type UserRole = "account_owner" | "admin" | "manager" | "member";
export type UserStatus = "active" | "inactive" | "pending";
export type WebsitePreference = "any" | "must_have" | "must_be_missing";
export type OutreachTone = "formal" | "friendly" | "consultative" | "short_pitch";
export type LeadSortOption = "newest" | "score_desc" | "reviews_desc" | "rating_desc";

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
  workspace_name: string;
  workspace_slug: string;
  email: string;
  full_name: string;
  role: UserRole;
  status: UserStatus;
  permissions: string[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthenticatedUser;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface SignupRequest {
  full_name: string;
  workspace_name: string;
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
  discovery_runtime: string;
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
  latest_qualified: boolean | null;
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
  tone: OutreachTone;
}

export interface OutreachDraftResponse {
  public_id: string;
  lead_id: string;
  ai_analysis_snapshot_public_id: string;
  subject: string;
  message: string;
  tone: OutreachTone;
  version_number: number;
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

export interface OutreachGenerateRequest {
  tone?: OutreachTone;
  regenerate?: boolean;
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

export interface PromptTemplateResponse {
  public_id: string;
  name: string;
  template_text: string;
  is_active: boolean;
  created_at: string;
  created_by_user_public_id: string;
}

export interface PromptTemplateListResponse {
  items: PromptTemplateResponse[];
}

export interface PromptTemplateCreateRequest {
  name: string;
  template_text: string;
  activate?: boolean;
}

export interface RecentFailedJobResponse {
  public_id: string;
  business_type: string;
  city: string;
  status: SearchJobStatus;
  queued_at: string;
  finished_at: string | null;
  provider_error_count: number;
}

export interface RecentProviderFailureResponse {
  public_id: string;
  engine: string;
  mode: string;
  status: string;
  http_status: number | null;
  error_message: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface OperationalHealthResponse {
  database_ok: boolean;
  serpapi_configured: boolean;
  serpapi_runtime_mode: string;
  discovery_runtime: string;
  analysis_runtime: string;
  demo_fallbacks_enabled: boolean;
  runtime_warnings: string[];
  failed_jobs_last_7_days: number;
  provider_failures_last_7_days: number;
  recent_failed_jobs: RecentFailedJobResponse[];
  recent_provider_failures: RecentProviderFailureResponse[];
}

export interface UserOption {
  public_id: string;
  email: string;
  full_name: string;
  role: UserRole;
  status: UserStatus;
  job_title?: string | null;
  last_login_at?: string | null;
  created_at?: string;
}

export interface UserListResponse {
  items: UserOption[];
}

export interface UserDetailResponse extends UserOption {
  workspace_public_id: string;
  invited_by_user_public_id?: string | null;
  avatar_url?: string | null;
  updated_at: string;
}

export interface UserCreateRequest {
  email: string;
  full_name: string;
  password: string;
  role: UserRole;
  job_title?: string | null;
  avatar_url?: string | null;
}

export interface UserUpdateRequest {
  full_name?: string;
  role?: UserRole;
  status?: UserStatus;
  job_title?: string | null;
  avatar_url?: string | null;
}

export interface UserPasswordResetRequest {
  password: string;
}

export interface WorkspaceSummary {
  public_id: string;
  name: string;
  slug: string;
  status: "active" | "suspended" | "disabled";
}

export interface WorkspaceSettingsResponse {
  workspace: WorkspaceSummary;
  owner_user_public_id?: string | null;
  settings: Record<string, unknown>;
}

export interface WorkspaceSettingsUpdateRequest {
  name?: string;
  slug?: string;
  settings?: Record<string, unknown>;
}

export interface PlanResponse {
  code: string;
  name: string;
  monthly_price: number;
  yearly_price: number;
  limits: Record<string, number>;
  is_active: boolean;
}

export interface PlanListResponse {
  items: PlanResponse[];
}

export interface SubscriptionResponse {
  public_id: string;
  plan_code: string;
  plan_name: string;
  status: "trialing" | "active" | "past_due" | "canceled" | "expired";
  billing_cycle: "monthly" | "yearly";
  started_at: string;
  ends_at?: string | null;
  renews_at?: string | null;
  canceled_at?: string | null;
  trial_ends_at?: string | null;
  simulated_payment_method: string;
}

export interface InvoiceItemResponse {
  description: string;
  amount: number;
  quantity: number;
}

export interface PaymentAttemptResponse {
  public_id: string;
  status: string;
  simulated_result: string;
  attempted_at: string;
  error_message?: string | null;
}

export interface InvoiceResponse {
  public_id: string;
  amount: number;
  currency: string;
  status: string;
  issued_at: string;
  due_at?: string | null;
  paid_at?: string | null;
  items: InvoiceItemResponse[];
  payment_attempts: PaymentAttemptResponse[];
}

export interface InvoiceListResponse {
  items: InvoiceResponse[];
}

export interface UsageMetricResponse {
  metric_key: string;
  current_value: number;
  limit_value?: number | null;
  period_start: string;
  period_end: string;
}

export interface UsageSummaryResponse {
  items: UsageMetricResponse[];
}

export interface SubscriptionChangeRequest {
  plan_code: string;
  billing_cycle: "monthly" | "yearly";
}

export interface BillingSimulationRequest {
  invoice_public_id: string;
  error_message?: string;
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
