export type UserRole =
  | "platform_admin"
  | "account_owner"
  | "admin"
  | "manager"
  | "member";
export type UserStatus = "active" | "inactive" | "pending";
export type WebsitePreference = "any" | "must_have" | "must_be_missing";
export type OutreachTone =
  | "formal"
  | "friendly"
  | "consultative"
  | "short_pitch";
export type LeadSortOption =
  | "newest"
  | "score_desc"
  | "reviews_desc"
  | "rating_desc";

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

export type LeadScoreBand =
  | "high"
  | "medium"
  | "low"
  | "not_qualified"
  | "hot_lead"
  | "warm_lead"
  | "research_more"
  | "low_priority"
  | "do_not_contact";

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
  email: string | null;
  email_confidence: number | null;
  linkedin_url: string | null;
  industry: string | null;
  employee_count: number | null;
  ai_opener: string | null;
  logo_url: string | null;
  status: LeadStatus;
  assigned_to_user_public_id: string | null;
  latest_score: number | null;
  latest_fit_score: number | null;
  latest_need_score: number | null;
  latest_urgency_score: number | null;
  latest_reachability_score: number | null;
  latest_final_priority_score: number | null;
  latest_band: LeadScoreBand | null;
  latest_qualified: boolean | null;
  latest_outreach_status: string | null;
  top_signal_type: string | null;
  top_signal_strength: number | null;
  top_signal_evidence: string | null;
  signals_count: number;
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
  fit_score: number | null;
  need_score: number | null;
  urgency_score: number | null;
  reachability_score: number | null;
  final_priority_score: number | null;
  band: LeadScoreBand;
  qualified: boolean;
  breakdown: ScoreBreakdownItem[];
}

export interface LeadSignalResponse {
  public_id: string;
  signal_type: string;
  signal_strength: number;
  evidence_text: string;
  source_url: string | null;
  detected_at: string;
}

export interface LeadSignalScoreResponse {
  signal_type: string;
  score: number;
  confidence: number;
  evidence_count: number;
  calculated_at: string;
}

export interface LeadSignalsResponse {
  lead_id: string;
  items: LeadSignalResponse[];
  scores: LeadSignalScoreResponse[];
}

export interface IcpProfileResponse {
  public_id: string;
  name: string;
  description: string | null;
  target_industries: string[];
  target_cities: string[];
  min_rating: number | null;
  max_rating: number | null;
  min_reviews: number | null;
  max_reviews: number | null;
  website_preference: WebsitePreference;
  required_signals: string[];
  excluded_keywords: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface IcpProfileListResponse {
  items: IcpProfileResponse[];
}

export interface IcpProfileCreateRequest {
  name: string;
  description?: string | null;
  target_industries?: string[];
  target_cities?: string[];
  min_rating?: number | null;
  max_rating?: number | null;
  min_reviews?: number | null;
  max_reviews?: number | null;
  website_preference?: WebsitePreference;
  required_signals?: string[];
  excluded_keywords?: string[];
  is_active?: boolean;
}

export type IcpProfileUpdateRequest = Partial<IcpProfileCreateRequest>;

export interface LeadIcpMatchResponse {
  public_id: string;
  lead_id: string;
  icp_profile_id: string;
  fit_score: number;
  matched: boolean;
  match_reasons: Record<string, unknown>;
  calculated_at: string;
}

export interface LeadIcpMatchListResponse {
  items: LeadIcpMatchResponse[];
}

export interface LeadAnalysisResult {
  summary: string;
  weaknesses: string[];
  opportunities: string[];
  recommended_services: string[];
  outreach_subject: string;
  outreach_message: string;
  confidence: number;
  recommended_tone?: string | null;
  pain_points?: string[];
  opportunity_reason?: string | null;
  outreach_angle?: string | null;
  risks_or_uncertainties?: string[];
  evidence_used?: string[];
}

export interface AIEvidenceItem {
  public_id: string;
  source_type: string;
  source_url: string | null;
  evidence_text: string;
  confidence: number;
  created_at: string;
}

export interface LeadAiEvidenceResponse {
  lead_id: string;
  snapshot_public_id: string | null;
  items: AIEvidenceItem[];
}

export type AIFeedbackRating = "useful" | "not_useful";

export interface AIFeedbackRequest {
  rating: AIFeedbackRating;
  correction_text?: string | null;
}

export interface AIFeedbackResponse {
  public_id: string;
  snapshot_public_id: string;
  rating: string;
  correction_text: string | null;
  created_at: string;
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
  language: string;
  version_number: number;
  generated_subject: string;
  generated_message: string;
  has_manual_edits: boolean;
  outreach_status: string;
  created_at: string;
  updated_at: string;
}

export interface OutreachSendResponse {
  status: string;
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

export type CampaignStatus =
  | "draft"
  | "active"
  | "paused"
  | "completed"
  | "archived";
export type CampaignLeadStatus =
  | "added"
  | "drafted"
  | "ready"
  | "skipped"
  | "removed";
export type SequenceChannel = "email" | "linkedin" | "whatsapp_note";

export interface CampaignResponse {
  public_id: string;
  name: string;
  description: string | null;
  icp_profile_id: string | null;
  status: CampaignStatus;
  lead_count: number;
  sequence_steps_count: number;
  created_at: string;
  updated_at: string;
}

export interface CampaignListResponse {
  items: CampaignResponse[];
}

export interface CampaignCreateRequest {
  name: string;
  description?: string | null;
  icp_profile_id?: string | null;
}

export interface CampaignUpdateRequest {
  name?: string;
  description?: string | null;
  status?: CampaignStatus;
}

export interface CampaignLeadAddRequest {
  lead_ids: string[];
}

export interface CampaignLeadResponse {
  lead: LeadResponse;
  status: CampaignLeadStatus;
  added_at: string;
}

export interface SequenceStepResponse {
  public_id: string;
  step_order: number;
  channel: SequenceChannel;
  delay_days: number;
  tone: string;
  language: string;
  template_text: string;
  created_at: string;
  updated_at: string;
}

export interface SequenceStepUpdateRequest {
  channel?: SequenceChannel;
  delay_days?: number;
  tone?: string;
  language?: string;
  template_text?: string;
}

export interface OutreachEventResponse {
  public_id: string;
  event_type: string;
  occurred_at: string;
  lead_id: string | null;
  outreach_message_id: string | null;
  metadata: Record<string, unknown> | null;
}

export interface CampaignDetailResponse extends CampaignResponse {
  leads: CampaignLeadResponse[];
  sequence_steps: SequenceStepResponse[];
  drafts: OutreachDraftResponse[];
  events: OutreachEventResponse[];
}

export interface CampaignGenerateDraftsResponse {
  created_count: number;
  drafts: OutreachDraftResponse[];
}

export interface CampaignActionResponse {
  status: string;
}

export type DealStatus = "open" | "won" | "lost" | "archived";
export type StageType = "open" | "won" | "lost";
export type ActivityType =
  | "note"
  | "call"
  | "meeting"
  | "email"
  | "follow_up"
  | "status_change";

export interface CrmStageResponse {
  public_id: string;
  name: string;
  position: number;
  probability: number;
  color: string;
  stage_type: StageType;
  deal_count: number;
  total_value: number;
  created_at: string;
  updated_at: string;
}

export interface CrmPipelineResponse {
  public_id: string;
  name: string;
  description: string | null;
  is_default: boolean;
  stages: CrmStageResponse[];
  created_at: string;
  updated_at: string;
}

export interface CrmPipelineListResponse {
  items: CrmPipelineResponse[];
}

export interface CrmActivityResponse {
  public_id: string;
  deal_id: string;
  activity_type: ActivityType;
  title: string;
  note: string | null;
  due_at: string | null;
  completed_at: string | null;
  actor_user_id: string | null;
  actor_full_name: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface CrmDealResponse {
  public_id: string;
  title: string;
  pipeline_id: string;
  pipeline_name: string;
  stage_id: string;
  stage_name: string;
  stage_probability: number;
  lead: LeadResponse;
  campaign_id: string | null;
  campaign_name: string | null;
  owner_user_id: string | null;
  owner_full_name: string | null;
  value_amount: number | null;
  currency: string;
  probability: number;
  status: DealStatus;
  lost_reason: string | null;
  expected_close_date: string | null;
  next_follow_up_at: string | null;
  last_activity_at: string | null;
  next_activity: CrmActivityResponse | null;
  overdue_activity_count: number;
  created_at: string;
  updated_at: string;
}

export interface CrmDealListResponse {
  items: CrmDealResponse[];
}

export interface CrmDealDetailResponse extends CrmDealResponse {
  activities: CrmActivityResponse[];
}

export interface CrmDealCreateRequest {
  lead_id: string;
  title?: string | null;
  pipeline_id?: string | null;
  stage_id?: string | null;
  campaign_id?: string | null;
  owner_user_id?: string | null;
  value_amount?: number | null;
  currency?: string;
  probability?: number | null;
  expected_close_date?: string | null;
  next_follow_up_at?: string | null;
  allow_duplicate_open?: boolean;
}

export interface CrmDealUpdateRequest {
  title?: string;
  stage_id?: string;
  owner_user_id?: string | null;
  value_amount?: number | null;
  currency?: string;
  probability?: number;
  status?: DealStatus;
  lost_reason?: string | null;
  expected_close_date?: string | null;
  next_follow_up_at?: string | null;
}

export interface CrmActivityCreateRequest {
  activity_type?: ActivityType;
  title: string;
  note?: string | null;
  due_at?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface CrmActivityUpdateRequest {
  activity_type?: ActivityType;
  title?: string;
  note?: string | null;
  due_at?: string | null;
  completed_at?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface CrmDealActionResponse {
  status: string;
  deal: CrmDealResponse | null;
}

export interface CampaignCreateDealsResponse {
  created_count: number;
  skipped_count: number;
  deals: CrmDealResponse[];
  skipped_lead_ids: string[];
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
  review_score: number;
  news_presence: number;
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
  serpapi_live_reachable: boolean;
  serpapi_runtime_mode: string;
  discovery_runtime: string;
  current_ai_runtime: string;
  analysis_runtime: string;
  analysis_fallback_runtime: string | null;
  ollama_configured: boolean;
  ollama_reachable: boolean;
  openai_configured: boolean;
  openai_fallback_configured: boolean;
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

export interface AdminUsageMetricResponse {
  metric_key: string;
  current_value: number;
}

export interface PlatformAdminOverviewResponse {
  total_workspaces: number;
  active_workspaces: number;
  disabled_workspaces: number;
  total_users: number;
  active_users: number;
  total_leads: number;
  total_search_jobs: number;
  failed_search_jobs: number;
  total_ai_analyses: number;
  total_evidence_rows: number;
  total_icp_profiles: number;
  total_signals: number;
  monthly_recurring_revenue: number;
  unpaid_invoices_count: number;
  provider_error_count: number;
  usage_by_metric: AdminUsageMetricResponse[];
}

export interface AdminWorkspaceSummaryResponse {
  public_id: string;
  name: string;
  slug: string;
  status: string;
  owner_public_id: string | null;
  owner_email: string | null;
  users_count: number;
  leads_count: number;
  plan_code: string | null;
  subscription_status: string | null;
  created_at: string;
}

export interface AdminWorkspaceListResponse {
  items: AdminWorkspaceSummaryResponse[];
}

export interface AdminUserSummaryResponse {
  public_id: string;
  full_name: string;
  email: string;
  role: string;
  status: string;
  workspace_public_id: string;
  workspace_name: string;
  last_login_at: string | null;
  created_at: string;
}

export interface AdminUserListResponse {
  items: AdminUserSummaryResponse[];
}

export interface AdminSubscriptionResponse {
  public_id: string;
  workspace_public_id: string;
  workspace_name: string;
  plan_code: string;
  plan_name: string;
  status: string;
  billing_cycle: string;
  started_at: string;
  renews_at: string | null;
  ends_at: string | null;
}

export interface AdminInvoiceResponse {
  public_id: string;
  workspace_public_id: string;
  workspace_name: string;
  amount: number;
  currency: string;
  status: string;
  issued_at: string;
  due_at: string | null;
  paid_at: string | null;
  items: InvoiceItemResponse[];
  payment_attempts: PaymentAttemptResponse[];
}

export interface AdminUsageCounterResponse {
  workspace_public_id: string;
  workspace_name: string;
  metric_key: string;
  current_value: number;
  period_start: string;
  period_end: string;
}

export interface AdminSearchJobResponse {
  public_id: string;
  workspace_public_id: string;
  workspace_name: string;
  business_type: string;
  city: string;
  status: SearchJobStatus;
  queued_at: string;
  finished_at: string | null;
  candidates_found: number;
  leads_upserted: number;
  provider_error_count: number;
}

export interface AdminAuditLogResponse {
  public_id: string;
  actor_user_public_id: string | null;
  event_name: string;
  details: string;
  created_at: string;
}

export interface AdminWorkspaceDetailResponse {
  workspace: AdminWorkspaceSummaryResponse;
  owner: AdminUserSummaryResponse | null;
  users: AdminUserSummaryResponse[];
  users_count: number;
  leads_count: number;
  searches_count: number;
  icp_profiles_count: number;
  signals_count: number;
  scoring_versions_count: number;
  lead_scores_count: number;
  ai_analyses_count: number;
  ai_evidence_count: number;
  ai_feedback_count: number;
  subscription: AdminSubscriptionResponse | null;
  invoices: AdminInvoiceResponse[];
  usage_counters: AdminUsageCounterResponse[];
  recent_jobs: AdminSearchJobResponse[];
  recent_provider_errors: AdminProviderFetchResponse[];
  recent_audit_logs: AdminAuditLogResponse[];
}

export interface AdminActionResponse {
  status: string;
}

export interface AdminPlanListResponse {
  items: PlanResponse[];
}

export interface AdminSubscriptionListResponse {
  items: AdminSubscriptionResponse[];
}

export interface AdminInvoiceListResponse {
  items: AdminInvoiceResponse[];
}

export interface AdminUsageListResponse {
  items: AdminUsageCounterResponse[];
  quota_override_supported: boolean;
  quota_override_todo: string;
}

export interface AdminProviderSettingResponse {
  workspace_public_id: string;
  workspace_name: string;
  hl: string;
  gl: string;
  google_domain: string;
  enrich_top_n: number;
}

export interface AdminProviderFetchResponse {
  public_id: string;
  workspace_public_id: string;
  workspace_name: string;
  provider: string;
  engine: string;
  mode: string;
  status: string;
  http_status: number | null;
  error_message: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface AdminProvidersResponse {
  settings: AdminProviderSettingResponse[];
  recent_fetches: AdminProviderFetchResponse[];
  recent_errors: AdminProviderFetchResponse[];
  success_count: number;
  failure_count: number;
}

export interface AdminSearchJobListResponse {
  items: AdminSearchJobResponse[];
}

export interface AdminAIFeedbackSummaryResponse {
  rating: string;
  count: number;
}

export interface AdminAIFeedbackResponse {
  public_id: string;
  workspace_public_id: string;
  rating: string;
  correction_text: string | null;
  created_at: string;
}

export interface AdminFlaggedAnalysisResponse {
  public_id: string;
  workspace_public_id: string;
  workspace_name: string;
  lead_public_id: string;
  lead_name: string;
  confidence: number;
  risks_or_uncertainties: string[];
  created_at: string;
}

export interface AdminAIUsageResponse {
  analyses_count: number;
  evidence_rows_count: number;
  feedback_counts: AdminAIFeedbackSummaryResponse[];
  latest_feedback: AdminAIFeedbackResponse[];
  flagged_analyses: AdminFlaggedAnalysisResponse[];
}

export interface AdminFeatureHealthResponse {
  icp_profiles_count: number;
  lead_signals_count: number;
  scoring_versions_count: number;
  lead_scores_count: number;
  ai_evidence_count: number;
  ai_feedback_count: number;
  top_signal_types: AdminUsageMetricResponse[];
  priority_band_distribution: AdminUsageMetricResponse[];
  failed_jobs: AdminSearchJobResponse[];
}
