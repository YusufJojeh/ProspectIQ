import type { Page, Route } from "@playwright/test";

export const MOCK_IDS = {
  primaryLeadId: "lead_acme_1",
  secondaryLeadId: "lead_north_1",
  seedJobId: "job_seed_1",
  workspaceId: "ws_default",
  adminEmail: "admin@prospectiq.dev",
  adminPassword: "ChangeMe123!",
  memberEmail: "sales@prospectiq.dev",
  memberPassword: "MemberPass123!",
  inactiveEmail: "inactive@prospectiq.dev",
  inactivePassword: "InactivePass123!",
} as const;

type UserRole = "account_owner" | "admin" | "manager" | "member";
type UserStatus = "active" | "inactive" | "pending";
type SearchJobStatus = "queued" | "running" | "completed" | "partially_completed" | "failed";
type LeadStatus =
  | "new"
  | "reviewed"
  | "qualified"
  | "contacted"
  | "interested"
  | "won"
  | "lost"
  | "archived";
type LeadScoreBand = "high" | "medium" | "low" | "not_qualified";
type WebsitePreference = "any" | "must_have" | "must_be_missing";
type OutreachTone = "formal" | "friendly" | "consultative" | "short_pitch";

type AuthenticatedUser = {
  public_id: string;
  workspace_public_id: string;
  workspace_name: string;
  workspace_slug: string;
  email: string;
  full_name: string;
  role: UserRole;
  status: UserStatus;
  permissions: string[];
};

type SearchJobResponse = {
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
};

type LeadRecord = {
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
  search_job_public_id: string | null;
};

type LeadEvidenceItem = {
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
};

type ScoreBreakdownItem = {
  key: string;
  label: string;
  weight: number;
  contribution: number;
  reason: string;
};

type LeadActivityEntry = {
  entry_id: string;
  entry_type: "status_change" | "note";
  actor_user_public_id: string | null;
  actor_full_name: string | null;
  created_at: string;
  from_status: LeadStatus | null;
  to_status: LeadStatus | null;
  note: string | null;
};

type LeadAnalysisResult = {
  summary: string;
  weaknesses: string[];
  opportunities: string[];
  recommended_services: string[];
  outreach_subject: string;
  outreach_message: string;
  confidence: number;
};

type LeadAnalysisSnapshot = {
  public_id: string;
  lead_id: string;
  ai_provider: string;
  model_name: string;
  created_at: string;
  analysis: LeadAnalysisResult;
  service_recommendations: Array<{
    public_id: string;
    service_name: string;
    rationale: string | null;
    confidence: number | null;
    rank_order: number;
    created_at: string;
  }>;
};

type OutreachDraft = {
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
};

type PromptTemplate = {
  public_id: string;
  name: string;
  template_text: string;
  is_active: boolean;
  created_at: string;
  created_by_user_public_id: string;
};

type ScoringConfigVersion = {
  public_id: string;
  weights: {
    local_trust: number;
    website_presence: number;
    search_visibility: number;
    opportunity: number;
    data_confidence: number;
  };
  thresholds: {
    high_min: number;
    medium_min: number;
    low_min: number;
    confidence_min: number;
  };
  note: string | null;
  created_at: string;
  created_by_user_public_id: string;
};

type AuditLogEntry = {
  public_id: string;
  actor_user_public_id: string | null;
  event_name: string;
  details: string;
  created_at: string;
};

export type MockState = {
  sessionUser: AuthenticatedUser;
  users: Array<{
    public_id: string;
    email: string;
    full_name: string;
    role: UserRole;
    status: UserStatus;
    job_title?: string | null;
    last_login_at?: string | null;
    created_at?: string;
  }>;
  searchJobs: SearchJobResponse[];
  leads: LeadRecord[];
  evidenceByLeadId: Record<string, { lead_id: string; items: LeadEvidenceItem[] }>;
  scoreBreakdownsByLeadId: Record<
    string,
    {
      lead_id: string;
      scoring_version_id: string;
      total_score: number;
      band: LeadScoreBand;
      qualified: boolean;
      breakdown: ScoreBreakdownItem[];
    }
  >;
  activityByLeadId: Record<string, LeadActivityEntry[]>;
  analysisByLeadId: Record<string, LeadAnalysisSnapshot | null>;
  outreachByLeadId: Record<string, OutreachDraft | null>;
  providerSettings: {
    hl: string;
    gl: string;
    google_domain: string;
    enrich_top_n: number;
  };
  promptTemplates: PromptTemplate[];
  scoringVersions: ScoringConfigVersion[];
  activeScoringVersionId: string;
  auditLogs: AuditLogEntry[];
  billing: {
    plans: Array<{
      code: string;
      name: string;
      monthly_price: number;
      yearly_price: number;
      limits: Record<string, number>;
      is_active: boolean;
    }>;
    subscription: {
      public_id: string;
      plan_code: string;
      plan_name: string;
      status: "trialing" | "active" | "past_due" | "canceled" | "expired";
      billing_cycle: "monthly" | "yearly";
      started_at: string;
      trial_ends_at: string | null;
      renews_at: string | null;
      simulated_payment_method: string;
    };
    usage: Array<{
      metric_key: string;
      current_value: number;
      limit_value: number;
      period_start: string;
      period_end: string;
    }>;
  };
  counters: {
    searchJobs: number;
    notes: number;
    analyses: number;
    recommendations: number;
    outreach: number;
    promptTemplates: number;
    scoringVersions: number;
    audit: number;
    timestamps: number;
  };
};

const CORS_HEADERS = {
  "access-control-allow-origin": "http://127.0.0.1:4173",
  "access-control-allow-methods": "GET,POST,PATCH,OPTIONS",
  "access-control-allow-headers": "Content-Type, Authorization",
};

const BASE_TIME = Date.parse("2026-04-03T12:00:00.000Z");

function iso(stepMinutes: number) {
  return new Date(BASE_TIME + stepMinutes * 60_000).toISOString();
}

function nextTimestamp(state: MockState) {
  state.counters.timestamps += 1;
  return iso(state.counters.timestamps);
}

function permissionsForRole(role: UserRole) {
  if (role === "account_owner") {
    return [
      "workspace:read",
      "workspace:update",
      "team:read",
      "team:manage",
      "billing:read",
      "billing:manage",
      "usage:read",
    ];
  }
  if (role === "admin") {
    return [
      "workspace:read",
      "team:read",
      "team:manage",
      "billing:read",
      "usage:read",
    ];
  }
  if (role === "manager") {
    return ["workspace:read", "team:read", "usage:read"];
  }
  return ["workspace:read"];
}

function serializeLead(lead: LeadRecord) {
  const { search_job_public_id: _searchJobPublicId, ...payload } = lead;
  return payload;
}

function readJsonBody(route: Route) {
  const payload = route.request().postData();
  if (!payload) {
    return {};
  }
  return JSON.parse(payload) as Record<string, unknown>;
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    headers: CORS_HEADERS,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function fulfillText(route: Route, body: string, contentType: string, status = 200) {
  await route.fulfill({
    status,
    headers: CORS_HEADERS,
    contentType,
    body,
  });
}

function createState(): MockState {
  const sessionUser: AuthenticatedUser = {
    public_id: "usr_admin_1",
    workspace_public_id: "ws_default",
    workspace_name: "Northbeam Agency",
    workspace_slug: "northbeam-agency",
    email: "admin@prospectiq.dev",
    full_name: "Admin User",
    role: "account_owner",
    status: "active",
    permissions: permissionsForRole("account_owner"),
  };

  const scoringVersion: ScoringConfigVersion = {
    public_id: "scv_active_1",
    weights: {
      local_trust: 0.25,
      website_presence: 0.25,
      search_visibility: 0.2,
      opportunity: 0.2,
      data_confidence: 0.1,
    },
    thresholds: {
      high_min: 75,
      medium_min: 55,
      low_min: 35,
      confidence_min: 0.45,
    },
    note: "Seeded active scoring policy",
    created_at: iso(1),
    created_by_user_public_id: sessionUser.public_id,
  };

  const promptTemplate: PromptTemplate = {
    public_id: "pt_active_1",
    name: "Default Lead Analysis",
    template_text:
      "Use only the supplied evidence, score breakdown, and service catalog. Do not invent unsupported facts.",
    is_active: true,
    created_at: iso(1),
    created_by_user_public_id: sessionUser.public_id,
  };

  const searchJobs: SearchJobResponse[] = [
    {
      public_id: "job_seed_1",
      discovery_runtime: "serpapi",
      business_type: "Dentist",
      city: "Istanbul",
      region: "Kadikoy",
      radius_km: 10,
      max_results: 25,
      min_rating: 4,
      max_rating: 5,
      min_reviews: 10,
      max_reviews: 250,
      website_preference: "must_have",
      keyword_filter: "implant",
      status: "completed",
      queued_at: iso(2),
      started_at: iso(3),
      finished_at: iso(7),
      candidates_found: 4,
      leads_upserted: 2,
      enriched_count: 2,
      provider_error_count: 0,
    },
  ];

  const leads: LeadRecord[] = [
    {
      public_id: "lead_acme_1",
      company_name: "Acme Dental",
      category: "Dentist",
      address: "Bagdat Avenue, Istanbul, Turkey",
      city: "Istanbul",
      phone: "+90 555 111 2233",
      website_url: "https://acmedental.example",
      website_domain: "acmedental.example",
      review_count: 24,
      rating: 4.7,
      lat: 41.015,
      lng: 29.042,
      data_completeness: 0.84,
      data_confidence: 0.88,
      has_website: true,
      status: "new",
      assigned_to_user_public_id: null,
      latest_score: 82.5,
      latest_band: "high",
      latest_qualified: true,
      created_at: iso(4),
      updated_at: iso(7),
      search_job_public_id: "job_seed_1",
    },
    {
      public_id: "lead_north_1",
      company_name: "North Clinic",
      category: "Clinic",
      address: "Tesvikiye, Istanbul, Turkey",
      city: "Istanbul",
      phone: "+90 555 999 8899",
      website_url: null,
      website_domain: null,
      review_count: 8,
      rating: 4.2,
      lat: 41.048,
      lng: 28.987,
      data_completeness: 0.68,
      data_confidence: 0.71,
      has_website: false,
      status: "reviewed",
      assigned_to_user_public_id: "usr_manager_1",
      latest_score: 61.5,
      latest_band: "medium",
      latest_qualified: true,
      created_at: iso(5),
      updated_at: iso(7),
      search_job_public_id: "job_seed_1",
    },
  ];

  return {
    sessionUser,
    users: [
      {
        public_id: sessionUser.public_id,
        email: sessionUser.email,
        full_name: sessionUser.full_name,
        role: sessionUser.role,
        status: "active",
        created_at: iso(1),
      },
      {
        public_id: "usr_manager_1",
        email: "manager@prospectiq.dev",
        full_name: "Manager User",
        role: "admin",
        status: "active",
        created_at: iso(2),
      },
      {
        public_id: "usr_sales_1",
        email: "sales@prospectiq.dev",
        full_name: "Sales User",
        role: "member",
        status: "active",
        created_at: iso(3),
      },
    ],
    searchJobs,
    leads,
    evidenceByLeadId: {
      lead_acme_1: {
        lead_id: "lead_acme_1",
        items: [
          {
            source_type: "maps_place",
            provider_fetch_public_id: "pf_1",
            provider_status: "ok",
            request_mode: "maps_place",
            http_status: 200,
            data_cid: "123456789",
            data_id: "0xabc:0xdef",
            place_id: "ChIJAcmeDental",
            company_name: "Acme Dental",
            category: "Dentist",
            address: "Bagdat Avenue, Istanbul, Turkey",
            city: "Istanbul",
            phone: "+90 555 111 2233",
            website_url: "https://acmedental.example",
            website_domain: "acmedental.example",
            rating: 4.7,
            review_count: 24,
            lat: 41.015,
            lng: 29.042,
            confidence: 0.88,
            completeness: 0.84,
            facts: {
              website: "https://acmedental.example",
              source: "maps_place",
            },
            created_at: iso(6),
          },
        ],
      },
      lead_north_1: {
        lead_id: "lead_north_1",
        items: [
          {
            source_type: "maps_search",
            provider_fetch_public_id: "pf_2",
            provider_status: "ok",
            request_mode: "maps_search",
            http_status: 200,
            data_cid: "987654321",
            data_id: "0xdef:0xabc",
            place_id: "ChIJNorthClinic",
            company_name: "North Clinic",
            category: "Clinic",
            address: "Tesvikiye, Istanbul, Turkey",
            city: "Istanbul",
            phone: "+90 555 999 8899",
            website_url: null,
            website_domain: null,
            rating: 4.2,
            review_count: 8,
            lat: 41.048,
            lng: 28.987,
            confidence: 0.71,
            completeness: 0.68,
            facts: {
              source: "maps_search",
            },
            created_at: iso(6),
          },
        ],
      },
    },
    scoreBreakdownsByLeadId: {
      lead_acme_1: {
        lead_id: "lead_acme_1",
        scoring_version_id: scoringVersion.public_id,
        total_score: 82.5,
        band: "high",
        qualified: true,
        breakdown: [
          {
            key: "website_presence",
            label: "Website presence",
            weight: 0.25,
            contribution: 21,
            reason: "An official website is present and discoverable.",
          },
          {
            key: "local_trust",
            label: "Local trust",
            weight: 0.25,
            contribution: 24,
            reason: "High rating with strong review volume.",
          },
        ],
      },
      lead_north_1: {
        lead_id: "lead_north_1",
        scoring_version_id: scoringVersion.public_id,
        total_score: 61.5,
        band: "medium",
        qualified: true,
        breakdown: [
          {
            key: "opportunity",
            label: "Opportunity",
            weight: 0.2,
            contribution: 18,
            reason: "Website is missing, creating a clear agency opportunity.",
          },
        ],
      },
    },
    activityByLeadId: {
      lead_acme_1: [],
      lead_north_1: [
        {
          entry_id: "status_seed_1",
          entry_type: "status_change",
          actor_user_public_id: "usr_manager_1",
          actor_full_name: "Manager User",
          created_at: iso(6),
          from_status: "new",
          to_status: "reviewed",
          note: null,
        },
      ],
    },
    analysisByLeadId: {
      lead_acme_1: null,
      lead_north_1: null,
    },
    outreachByLeadId: {
      lead_acme_1: null,
      lead_north_1: null,
    },
    providerSettings: {
      hl: "en",
      gl: "tr",
      google_domain: "google.com",
      enrich_top_n: 20,
    },
    promptTemplates: [promptTemplate],
    scoringVersions: [scoringVersion],
    activeScoringVersionId: scoringVersion.public_id,
    auditLogs: [
      {
        public_id: "log_seed_1",
        actor_user_public_id: sessionUser.public_id,
        event_name: "search.job_created",
        details: "Queued the sample Istanbul dentist discovery run.",
        created_at: iso(8),
      },
    ],
    billing: {
      plans: [
        {
          code: "starter",
          name: "Starter",
          monthly_price: 49,
          yearly_price: 490,
          limits: {
            searches_per_month: 50,
            exports_per_month: 25,
            ai_scoring_runs_per_month: 100,
            outreach_generations_per_month: 150,
            max_team_users: 5,
          },
          is_active: true,
        },
        {
          code: "growth",
          name: "Growth",
          monthly_price: 149,
          yearly_price: 1490,
          limits: {
            searches_per_month: 250,
            exports_per_month: 100,
            ai_scoring_runs_per_month: 500,
            outreach_generations_per_month: 700,
            max_team_users: 10,
          },
          is_active: true,
        },
      ],
      subscription: {
        public_id: "sub_mock_1",
        plan_code: "starter",
        plan_name: "Starter",
        status: "trialing",
        billing_cycle: "monthly",
        started_at: iso(1),
        trial_ends_at: iso(1440),
        renews_at: iso(1440),
        simulated_payment_method: "Simulated card ending in 4242",
      },
      usage: [
        {
          metric_key: "searches_per_month",
          current_value: 1,
          limit_value: 50,
          period_start: iso(0),
          period_end: iso(43200),
        },
        {
          metric_key: "max_team_users",
          current_value: 3,
          limit_value: 5,
          period_start: iso(0),
          period_end: iso(43200),
        },
      ],
    },
    counters: {
      searchJobs: 1,
      notes: 0,
      analyses: 0,
      recommendations: 0,
      outreach: 0,
      promptTemplates: 1,
      scoringVersions: 1,
      audit: 1,
      timestamps: 8,
    },
  };
}

function addAudit(state: MockState, eventName: string, details: string) {
  state.counters.audit += 1;
  state.auditLogs.unshift({
    public_id: `log_mock_${state.counters.audit}`,
    actor_user_public_id: state.sessionUser.public_id,
    event_name: eventName,
    details,
    created_at: nextTimestamp(state),
  });
}

function getLeadOrThrow(state: MockState, leadId: string) {
  const lead = state.leads.find((item) => item.public_id === leadId);
  if (!lead) {
    throw new Error(`Unknown mocked lead '${leadId}'.`);
  }
  return lead;
}

function ensureAnalysis(state: MockState, leadId: string) {
  const existing = state.analysisByLeadId[leadId];
  if (existing) {
    return existing;
  }

  const lead = getLeadOrThrow(state, leadId);
  state.counters.analyses += 1;
  const createdAt = nextTimestamp(state);
  const analysis: LeadAnalysisSnapshot = {
    public_id: `ais_mock_${state.counters.analyses}`,
    lead_id: leadId,
    ai_provider: "stub",
    model_name: "deterministic-rules-v1",
    created_at: createdAt,
    analysis: {
      summary: `${lead.company_name} has a strong local profile but still has clear visibility improvements to pursue first.`,
      weaknesses: [
        "The business profile needs stronger differentiation across local search surfaces.",
        "Review response hygiene and proof points can be improved further.",
      ],
      opportunities: [
        "Tighten the GBP and on-site conversion flow around high-intent service terms.",
        "Use local SEO and review ops to increase trust signals before outreach.",
      ],
      recommended_services: [
        "Google Business Profile Optimization",
        "Local SEO Sprint",
        "Reputation Management",
      ],
      outreach_subject: `Quick visibility idea for ${lead.company_name}`,
      outreach_message: `Hi ${lead.company_name},\n\nWe reviewed your current local search footprint and found two evidence-backed opportunities that could improve qualified lead flow in the near term.\n\nWould you like a short audit summary?`,
      confidence: 0.79,
    },
    service_recommendations: [
      "Google Business Profile Optimization",
      "Local SEO Sprint",
      "Reputation Management",
    ].map((serviceName, index) => {
      state.counters.recommendations += 1;
      return {
        public_id: `srv_mock_${state.counters.recommendations}`,
        service_name: serviceName,
        rationale: null,
        confidence: 0.79,
        rank_order: index + 1,
        created_at: createdAt,
      };
    }),
  };

  state.analysisByLeadId[leadId] = analysis;
  addAudit(state, "lead.analyzed", `Generated an assistive analysis for lead ${leadId}.`);
  return analysis;
}

function buildOutreachCopy(
  leadName: string,
  tone: OutreachTone,
): { subject: string; message: string } {
  if (tone === "formal") {
    return {
      subject: `Visibility assessment for ${leadName}`,
      message: `Hello,\n\nWe reviewed ${leadName}'s local search presence and identified several evidence-backed improvements that could strengthen qualified lead acquisition.\n\nIf useful, we can share a concise assessment.`,
    };
  }
  if (tone === "friendly") {
    return {
      subject: `A quick growth idea for ${leadName}`,
      message: `Hi ${leadName},\n\nWe took a quick look at your local search footprint and found a few practical improvements that could help more nearby customers find you.\n\nHappy to send over the short version.`,
    };
  }
  if (tone === "short_pitch") {
    return {
      subject: `${leadName}: two quick visibility wins`,
      message: `Hi ${leadName}, we found two evidence-backed local visibility fixes that could improve inbound lead flow. Want the short audit?`,
    };
  }
  return {
    subject: `Quick visibility idea for ${leadName}`,
    message: `Hi ${leadName},\n\nWe reviewed your current local search footprint and found two evidence-backed opportunities that could improve qualified lead flow in the near term.\n\nWould you like a short audit summary?`,
  };
}

function ensureOutreach(
  state: MockState,
  leadId: string,
  options?: { tone?: OutreachTone; regenerate?: boolean },
) {
  const requestedTone = options?.tone ?? "consultative";
  const existing = state.outreachByLeadId[leadId];
  if (existing && !options?.regenerate && existing.tone === requestedTone) {
    return existing;
  }

  const analysis = ensureAnalysis(state, leadId);
  const lead = getLeadOrThrow(state, leadId);
  const { subject, message } = buildOutreachCopy(lead.company_name, requestedTone);
  state.counters.outreach += 1;
  const createdAt = nextTimestamp(state);
  const draft: OutreachDraft = {
    public_id: `om_mock_${state.counters.outreach}`,
    lead_id: leadId,
    ai_analysis_snapshot_public_id: analysis.public_id,
    subject,
    message,
    tone: requestedTone,
    version_number: (existing?.version_number ?? 0) + 1,
    generated_subject: subject,
    generated_message: message,
    has_manual_edits: false,
    created_at: createdAt,
    updated_at: createdAt,
  };

  state.outreachByLeadId[leadId] = draft;
  addAudit(state, "lead.outreach_generated", `Generated an outreach draft for lead ${leadId}.`);
  return draft;
}

function filterLeads(state: MockState, url: URL) {
  const q = url.searchParams.get("q")?.toLowerCase() ?? null;
  const city = url.searchParams.get("city")?.toLowerCase() ?? null;
  const category = url.searchParams.get("category")?.toLowerCase() ?? null;
  const status = url.searchParams.get("status");
  const band = url.searchParams.get("band");
  const minScore = url.searchParams.get("min_score");
  const maxScore = url.searchParams.get("max_score");
  const qualified = url.searchParams.get("qualified");
  const ownerUserId = url.searchParams.get("owner_user_id");
  const searchJobId = url.searchParams.get("search_job_id");
  const hasWebsite = url.searchParams.get("has_website");
  const sort = url.searchParams.get("sort") ?? "newest";
  const leadIds = url.searchParams.getAll("lead_ids");

  return [...state.leads]
    .filter((lead) => {
      if (leadIds.length > 0 && !leadIds.includes(lead.public_id)) {
        return false;
      }
      if (q) {
        const haystack = [lead.company_name, lead.city ?? "", lead.website_domain ?? "", lead.address ?? ""]
          .join(" ")
          .toLowerCase();
        if (!haystack.includes(q)) {
          return false;
        }
      }
      if (city && !(lead.city ?? "").toLowerCase().includes(city)) {
        return false;
      }
      if (category && !(lead.category ?? "").toLowerCase().includes(category)) {
        return false;
      }
      if (status && lead.status !== status) {
        return false;
      }
      if (band && lead.latest_band !== band) {
        return false;
      }
      if (minScore !== null && (lead.latest_score ?? 0) < Number(minScore)) {
        return false;
      }
      if (maxScore !== null && (lead.latest_score ?? 0) > Number(maxScore)) {
        return false;
      }
      if (qualified === "true" && !lead.latest_qualified) {
        return false;
      }
      if (qualified === "false" && lead.latest_qualified !== false) {
        return false;
      }
      if (ownerUserId && ownerUserId !== "all" && lead.assigned_to_user_public_id !== ownerUserId) {
        return false;
      }
      if (searchJobId && searchJobId !== "all" && lead.search_job_public_id !== searchJobId) {
        return false;
      }
      if (hasWebsite === "true" && !lead.has_website) {
        return false;
      }
      if (hasWebsite === "false" && lead.has_website) {
        return false;
      }
      return true;
    })
    .sort((left, right) => {
      if (sort === "score_desc") {
        return (right.latest_score ?? -1) - (left.latest_score ?? -1);
      }
      if (sort === "reviews_desc") {
        return right.review_count - left.review_count;
      }
      if (sort === "rating_desc") {
        return (right.rating ?? -1) - (left.rating ?? -1);
      }
      return Date.parse(right.created_at) - Date.parse(left.created_at);
    });
}

async function handleApiRoute(route: Route, state: MockState) {
  const request = route.request();
  const method = request.method();
  const url = new URL(request.url());
  const path = url.pathname;

  if (method === "OPTIONS") {
    await route.fulfill({
      status: 204,
      headers: CORS_HEADERS,
      body: "",
    });
    return;
  }

  if (path === "/api/v1/auth/login" && method === "POST") {
    const payload = readJsonBody(route);
    const email = String(payload.email ?? "").trim().toLowerCase();
    const password = String(payload.password ?? "");
    const credentialMap: Record<
      string,
      {
        password: string;
        public_id: string;
        full_name: string;
        role: UserRole;
        status: UserStatus;
      }
    > = {
      [MOCK_IDS.adminEmail]: {
        password: MOCK_IDS.adminPassword,
        public_id: "usr_admin_1",
        full_name: "Admin User",
        role: "account_owner",
        status: "active",
      },
      [MOCK_IDS.memberEmail]: {
        password: MOCK_IDS.memberPassword,
        public_id: "usr_sales_1",
        full_name: "Sales User",
        role: "member",
        status: "active",
      },
      [MOCK_IDS.inactiveEmail]: {
        password: MOCK_IDS.inactivePassword,
        public_id: "usr_inactive_1",
        full_name: "Inactive User",
        role: "member",
        status: "inactive",
      },
    };
    const record = credentialMap[email];
    if (!record || record.password !== password) {
      await fulfillJson(route, { error: { code: "invalid_credentials", detail: "Invalid email or password." } }, 401);
      return;
    }
    if (record.status !== "active") {
      await fulfillJson(
        route,
        {
          error: {
            code: "inactive_user",
            detail: "Your account is inactive. Contact your workspace administrator.",
          },
        },
        403,
      );
      return;
    }
    state.sessionUser = {
      ...state.sessionUser,
      public_id: record.public_id,
      email: email,
      full_name: record.full_name,
      role: record.role,
      status: record.status,
      permissions: permissionsForRole(record.role),
    };
    await fulfillJson(route, {
      access_token: "mock-access-token",
      token_type: "bearer",
      expires_in: 3600,
      user: state.sessionUser,
    });
    return;
  }

  if (path === "/api/v1/auth/signup" && method === "POST") {
    const payload = readJsonBody(route);
    state.sessionUser = {
      ...state.sessionUser,
      public_id: "usr_signup_1",
      full_name: String(payload.full_name ?? "New Owner"),
      email: String(payload.email ?? "owner@prospectiq.dev"),
      workspace_name: String(payload.workspace_name ?? "New Workspace"),
      workspace_slug: String(payload.workspace_name ?? "new-workspace").toLowerCase().replace(/\s+/g, "-"),
      role: "account_owner",
      status: "active",
      permissions: permissionsForRole("account_owner"),
    };
    await fulfillJson(route, {
      access_token: "mock-access-token",
      token_type: "bearer",
      expires_in: 3600,
      user: state.sessionUser,
    });
    return;
  }

  if ((path === "/api/v1/me" || path === "/api/v1/auth/me") && method === "GET") {
    await fulfillJson(route, state.sessionUser);
    return;
  }

  if (path === "/api/v1/users" && method === "GET") {
    await fulfillJson(route, { items: state.users });
    return;
  }

  if (path === "/api/v1/users" && method === "POST") {
    const payload = readJsonBody(route);
    const newUser = {
      public_id: `usr_mock_${state.users.length + 1}`,
      email: String(payload.email ?? "new@prospectiq.dev"),
      full_name: String(payload.full_name ?? "New User"),
      role: (payload.role as UserRole | undefined) ?? "member",
      status: "active" as UserStatus,
      created_at: nextTimestamp(state),
    };
    state.users.push(newUser);
    const teamUsage = state.billing.usage.find((item) => item.metric_key === "max_team_users");
    if (teamUsage) {
      teamUsage.current_value = state.users.length;
    }
    addAudit(state, "user.created", `Created user ${newUser.public_id} (${newUser.role}).`);
    await fulfillJson(route, newUser, 201);
    return;
  }

  const updateUserMatch = path.match(/^\/api\/v1\/users\/([^/]+)$/);
  if (updateUserMatch && method === "PATCH") {
    const payload = readJsonBody(route);
    const userId = updateUserMatch[1];
    const target = state.users.find((item) => item.public_id === userId);
    if (!target) {
      await fulfillJson(route, { error: { detail: "User not found." } }, 404);
      return;
    }
    if (typeof payload.status === "string") {
      target.status = payload.status as UserStatus;
    }
    if (typeof payload.role === "string") {
      target.role = payload.role as UserRole;
    }
    addAudit(state, "user.updated", `Updated user ${userId}.`);
    await fulfillJson(route, {
      ...target,
      workspace_public_id: state.sessionUser.workspace_public_id,
      updated_at: nextTimestamp(state),
    });
    return;
  }

  const resetPasswordMatch = path.match(/^\/api\/v1\/users\/([^/]+)\/reset-password$/);
  if (resetPasswordMatch && method === "POST") {
    const userId = resetPasswordMatch[1];
    const target = state.users.find((item) => item.public_id === userId);
    if (!target) {
      await fulfillJson(route, { error: { detail: "User not found." } }, 404);
      return;
    }
    addAudit(state, "user.password_reset", `Reset password for ${userId}.`);
    await fulfillJson(route, {
      ...target,
      workspace_public_id: state.sessionUser.workspace_public_id,
      updated_at: nextTimestamp(state),
    });
    return;
  }

  const searchJobByIdMatch = path.match(/^\/api\/v1\/search-jobs\/([^/]+)$/);
  if (searchJobByIdMatch && method === "GET") {
    const jobId = searchJobByIdMatch[1];
    const job = state.searchJobs.find((item) => item.public_id === jobId);
    if (!job) {
      await fulfillJson(route, { error: { code: "not_found", detail: "Search job was not found." } }, 404);
      return;
    }
    await fulfillJson(route, job);
    return;
  }

  if (path === "/api/v1/search-jobs" && method === "GET") {
    await fulfillJson(route, { items: state.searchJobs });
    return;
  }

  if (path === "/api/v1/search-jobs" && method === "POST") {
    const payload = readJsonBody(route);
    state.counters.searchJobs += 1;
    const now = nextTimestamp(state);
    const job: SearchJobResponse = {
      public_id: `job_mock_${state.counters.searchJobs}`,
      discovery_runtime: "serpapi",
      business_type: String(payload.business_type ?? "Unknown"),
      city: String(payload.city ?? "Unknown"),
      region: (payload.region as string | undefined) ?? null,
      radius_km: typeof payload.radius_km === "number" ? payload.radius_km : null,
      max_results: Number(payload.max_results ?? 25),
      min_rating: typeof payload.min_rating === "number" ? payload.min_rating : null,
      max_rating: typeof payload.max_rating === "number" ? payload.max_rating : null,
      min_reviews: typeof payload.min_reviews === "number" ? payload.min_reviews : null,
      max_reviews: typeof payload.max_reviews === "number" ? payload.max_reviews : null,
      website_preference: (payload.website_preference as WebsitePreference | undefined) ?? "any",
      keyword_filter: (payload.keyword_filter as string | undefined) ?? null,
      status: "queued",
      queued_at: now,
      started_at: null,
      finished_at: null,
      candidates_found: 0,
      leads_upserted: 0,
      enriched_count: 0,
      provider_error_count: 0,
    };
    state.searchJobs.unshift(job);
    addAudit(
      state,
      "search.job_created",
      `Queued a discovery job for ${job.business_type} in ${job.city}.`,
    );
    await fulfillJson(route, job, 202);
    return;
  }

  if (path === "/api/v1/leads" && method === "GET") {
    const filtered = filterLeads(state, url).map(serializeLead);
    const pageSize = Number(url.searchParams.get("page_size") ?? 20);
    const page = Number(url.searchParams.get("page") ?? 1);
    const total = filtered.length;
    const start = Math.max(0, (page - 1) * pageSize);
    const items = filtered.slice(start, start + pageSize);
    await fulfillJson(route, {
      items,
      pagination: {
        page,
        page_size: pageSize,
        total,
      },
    });
    return;
  }

  if (path === "/api/v1/exports/leads.csv" && method === "GET") {
    const filteredLeads = filterLeads(state, url);
    const rows = [
      "company_name,city,status,latest_score,website_domain",
      ...filteredLeads.map((lead) =>
        [
          lead.company_name,
          lead.city ?? "",
          lead.status,
          lead.latest_score ?? "",
          lead.website_domain ?? "",
        ].join(","),
      ),
    ];
    await fulfillText(route, rows.join("\n"), "text/csv");
    return;
  }

  if (path === "/api/v1/admin/provider-settings" && method === "GET") {
    await fulfillJson(route, state.providerSettings);
    return;
  }

  if (path === "/api/v1/workspace-settings" && method === "GET") {
    await fulfillJson(route, {
      workspace: {
        public_id: state.sessionUser.workspace_public_id,
        name: state.sessionUser.workspace_name,
        slug: state.sessionUser.workspace_slug,
        status: "active",
      },
      owner_user_public_id: state.sessionUser.public_id,
      settings: {
        locale: "en-US",
        theme: "dark",
      },
    });
    return;
  }

  if (path === "/api/v1/workspace-settings" && method === "PATCH") {
    const payload = readJsonBody(route);
    if (typeof payload.name === "string") {
      state.sessionUser.workspace_name = payload.name;
    }
    if (typeof payload.slug === "string") {
      state.sessionUser.workspace_slug = payload.slug;
    }
    addAudit(state, "workspace.updated", "Updated workspace settings.");
    await fulfillJson(route, {
      workspace: {
        public_id: state.sessionUser.workspace_public_id,
        name: state.sessionUser.workspace_name,
        slug: state.sessionUser.workspace_slug,
        status: "active",
      },
      owner_user_public_id: state.sessionUser.public_id,
      settings: {
        locale: "en-US",
        theme: "dark",
      },
    });
    return;
  }

  if (path === "/api/v1/billing/plans" && method === "GET") {
    await fulfillJson(route, { items: state.billing.plans });
    return;
  }

  if (path === "/api/v1/billing/subscription" && method === "GET") {
    await fulfillJson(route, state.billing.subscription);
    return;
  }

  if (path === "/api/v1/billing/invoices" && method === "GET") {
    await fulfillJson(route, {
      items: [
        {
          public_id: "inv_mock_1",
          amount: state.billing.subscription.plan_code === "growth" ? 149 : 49,
          currency: "USD",
          status: state.billing.subscription.status === "past_due" ? "past_due" : "open",
          issued_at: iso(10),
          due_at: iso(1440),
          paid_at: null,
          items: [
            {
              description: `${state.billing.subscription.plan_name} simulated subscription`,
              amount: state.billing.subscription.plan_code === "growth" ? 149 : 49,
              quantity: 1,
            },
          ],
          payment_attempts: [],
        },
      ],
    });
    return;
  }

  if (path === "/api/v1/billing/usage" && method === "GET") {
    await fulfillJson(route, { items: state.billing.usage });
    return;
  }

  if (path === "/api/v1/billing/subscription/change" && method === "POST") {
    const payload = readJsonBody(route);
    const plan = state.billing.plans.find((item) => item.code === payload.plan_code) ?? state.billing.plans[0];
    state.billing.subscription.plan_code = plan.code;
    state.billing.subscription.plan_name = plan.name;
    state.billing.subscription.billing_cycle = (payload.billing_cycle as "monthly" | "yearly" | undefined) ?? "monthly";
    addAudit(state, "billing.subscription_changed", `Changed plan to ${plan.code}.`);
    await fulfillJson(route, state.billing.subscription);
    return;
  }

  if (path === "/api/v1/billing/subscription/cancel" && method === "POST") {
    state.billing.subscription.status = "canceled";
    addAudit(state, "billing.subscription_canceled", "Canceled subscription.");
    await fulfillJson(route, state.billing.subscription);
    return;
  }

  if (path === "/api/v1/billing/subscription/renew" && method === "POST") {
    state.billing.subscription.status = "active";
    addAudit(state, "billing.subscription_renewed", "Renewed subscription.");
    await fulfillJson(route, state.billing.subscription);
    return;
  }

  if (path === "/api/v1/billing/invoices/mark-paid" && method === "POST") {
    addAudit(state, "billing.invoice_paid", "Marked invoice paid.");
    await fulfillJson(route, {
      public_id: "inv_mock_1",
      amount: state.billing.subscription.plan_code === "growth" ? 149 : 49,
      currency: "USD",
      status: "paid",
      issued_at: iso(10),
      due_at: iso(1440),
      paid_at: nextTimestamp(state),
      items: [],
      payment_attempts: [],
    });
    return;
  }

  if (path === "/api/v1/billing/invoices/simulate-failure" && method === "POST") {
    state.billing.subscription.status = "past_due";
    addAudit(state, "billing.payment_failed", "Simulated payment failure.");
    await fulfillJson(route, {
      public_id: "inv_mock_1",
      amount: state.billing.subscription.plan_code === "growth" ? 149 : 49,
      currency: "USD",
      status: "past_due",
      issued_at: iso(10),
      due_at: iso(1440),
      paid_at: null,
      items: [],
      payment_attempts: [],
    });
    return;
  }

  if (path === "/api/v1/admin/provider-settings" && method === "PATCH") {
    const payload = readJsonBody(route);
    state.providerSettings = {
      ...state.providerSettings,
      ...(payload as Partial<typeof state.providerSettings>),
    };
    addAudit(state, "admin.provider_settings_updated", "Updated provider defaults.");
    await fulfillJson(route, state.providerSettings);
    return;
  }

  if (path === "/api/v1/admin/prompt-templates" && method === "GET") {
    await fulfillJson(route, { items: state.promptTemplates });
    return;
  }

  if (path === "/api/v1/admin/prompt-templates" && method === "POST") {
    const payload = readJsonBody(route);
    state.counters.promptTemplates += 1;
    const activate = Boolean(payload.activate ?? true);
    if (activate) {
      state.promptTemplates = state.promptTemplates.map((item) => ({ ...item, is_active: false }));
    }
    const template: PromptTemplate = {
      public_id: `pt_mock_${state.counters.promptTemplates}`,
      name: String(payload.name ?? "Untitled template"),
      template_text: String(payload.template_text ?? ""),
      is_active: activate,
      created_at: nextTimestamp(state),
      created_by_user_public_id: state.sessionUser.public_id,
    };
    state.promptTemplates.unshift(template);
    addAudit(state, "admin.prompt_template_created", `Created prompt template ${template.public_id}.`);
    await fulfillJson(route, template);
    return;
  }

  const activatePromptTemplateMatch = path.match(/^\/api\/v1\/admin\/prompt-templates\/activate\/([^/]+)$/);
  if (activatePromptTemplateMatch && method === "POST") {
    const promptTemplateId = activatePromptTemplateMatch[1];
    state.promptTemplates = state.promptTemplates.map((item) => ({
      ...item,
      is_active: item.public_id === promptTemplateId,
    }));
    const activeTemplate = state.promptTemplates.find((item) => item.public_id === promptTemplateId);
    addAudit(state, "admin.prompt_template_activated", `Activated prompt template ${promptTemplateId}.`);
    await fulfillJson(route, activeTemplate);
    return;
  }

  if (path === "/api/v1/admin/operations/health" && method === "GET") {
    await fulfillJson(route, {
      database_ok: true,
      serpapi_configured: true,
      serpapi_runtime_mode: "auto",
      discovery_runtime: "serpapi",
      analysis_runtime: "demo",
      demo_fallbacks_enabled: true,
      runtime_warnings: [],
      failed_jobs_last_7_days: state.searchJobs.filter((job) => job.status === "failed").length,
      provider_failures_last_7_days: state.searchJobs.reduce(
        (count, job) => count + (job.provider_error_count > 0 ? 1 : 0),
        0,
      ),
      recent_failed_jobs: state.searchJobs
        .filter((job) => job.status === "failed")
        .slice(0, 5)
        .map((job) => ({
          public_id: job.public_id,
          business_type: job.business_type,
          city: job.city,
          status: job.status,
          queued_at: job.queued_at,
          finished_at: job.finished_at,
          provider_error_count: job.provider_error_count,
        })),
      recent_provider_failures: state.searchJobs
        .filter((job) => job.provider_error_count > 0)
        .slice(0, 5)
        .map((job) => ({
          public_id: `pf_failure_${job.public_id}`,
          engine: "google_maps_search",
          mode: "sync",
          status: "error",
          http_status: 429,
          error_message: `Provider failures recorded for ${job.business_type} / ${job.city}.`,
          started_at: job.started_at ?? job.queued_at,
          finished_at: job.finished_at,
        })),
    });
    return;
  }

  if (path === "/api/v1/admin/scoring-config/active" && method === "GET") {
    const activeVersion = state.scoringVersions.find(
      (item) => item.public_id === state.activeScoringVersionId,
    );
    await fulfillJson(route, { active_version: activeVersion });
    return;
  }

  if (path === "/api/v1/admin/scoring-config/versions" && method === "GET") {
    await fulfillJson(route, { items: state.scoringVersions });
    return;
  }

  if (path === "/api/v1/admin/scoring-config/versions" && method === "POST") {
    const payload = readJsonBody(route);
    state.counters.scoringVersions += 1;
    const version: ScoringConfigVersion = {
      public_id: `scv_mock_${state.counters.scoringVersions}`,
      weights: payload.weights as ScoringConfigVersion["weights"],
      thresholds: payload.thresholds as ScoringConfigVersion["thresholds"],
      note: (payload.note as string | undefined) ?? null,
      created_at: nextTimestamp(state),
      created_by_user_public_id: state.sessionUser.public_id,
    };
    state.scoringVersions.unshift(version);
    addAudit(state, "admin.scoring_version_created", `Created scoring version ${version.public_id}.`);
    await fulfillJson(route, version);
    return;
  }

  const activateScoringMatch = path.match(/^\/api\/v1\/admin\/scoring-config\/activate\/([^/]+)$/);
  if (activateScoringMatch && method === "POST") {
    state.activeScoringVersionId = activateScoringMatch[1];
    addAudit(
      state,
      "admin.scoring_version_activated",
      `Activated scoring version ${state.activeScoringVersionId}.`,
    );
    const activeVersion = state.scoringVersions.find(
      (item) => item.public_id === state.activeScoringVersionId,
    );
    await fulfillJson(route, { active_version: activeVersion });
    return;
  }

  if (path === "/api/v1/audit-logs" && method === "GET") {
    await fulfillJson(route, { items: state.auditLogs.slice(0, 50) });
    return;
  }

  const analysisLatestMatch = path.match(/^\/api\/v1\/ai-analysis\/leads\/([^/]+)\/latest$/);
  if (analysisLatestMatch && method === "GET") {
    const leadId = analysisLatestMatch[1];
    await fulfillJson(route, {
      lead_id: leadId,
      snapshot: state.analysisByLeadId[leadId] ?? null,
    });
    return;
  }

  const analysisGenerateMatch = path.match(/^\/api\/v1\/ai-analysis\/leads\/([^/]+)\/generate$/);
  if (analysisGenerateMatch && method === "POST") {
    const leadId = analysisGenerateMatch[1];
    await fulfillJson(route, ensureAnalysis(state, leadId));
    return;
  }

  const outreachLatestMatch = path.match(/^\/api\/v1\/outreach\/leads\/([^/]+)\/latest$/);
  if (outreachLatestMatch && method === "GET") {
    const leadId = outreachLatestMatch[1];
    await fulfillJson(route, {
      lead_id: leadId,
      message: state.outreachByLeadId[leadId] ?? null,
    });
    return;
  }

  const outreachGenerateMatch = path.match(/^\/api\/v1\/outreach\/leads\/([^/]+)\/generate$/);
  if (outreachGenerateMatch && method === "POST") {
    const leadId = outreachGenerateMatch[1];
    const payload = readJsonBody(route);
    await fulfillJson(route, ensureOutreach(state, leadId, {
      tone: payload.tone as OutreachTone | undefined,
      regenerate: Boolean(payload.regenerate),
    }));
    return;
  }

  const outreachUpdateMatch = path.match(/^\/api\/v1\/outreach\/messages\/([^/]+)$/);
  if (outreachUpdateMatch && method === "PATCH") {
    const payload = readJsonBody(route);
    const messageId = outreachUpdateMatch[1];
    const message = Object.values(state.outreachByLeadId).find(
      (item): item is OutreachDraft => Boolean(item && item.public_id === messageId),
    );
    if (!message) {
      await fulfillJson(route, { error: { detail: "Message not found." } }, 404);
      return;
    }
    message.subject = String(payload.subject ?? message.subject);
    message.message = String(payload.message ?? message.message);
    message.has_manual_edits = true;
    message.updated_at = nextTimestamp(state);
    addAudit(state, "lead.outreach_updated", `Updated outreach draft ${message.public_id}.`);
    await fulfillJson(route, message);
    return;
  }

  const leadActivityMatch = path.match(/^\/api\/v1\/leads\/([^/]+)\/activity$/);
  if (leadActivityMatch && method === "GET") {
    const leadId = leadActivityMatch[1];
    await fulfillJson(route, {
      lead_id: leadId,
      items: state.activityByLeadId[leadId] ?? [],
    });
    return;
  }

  const leadAnalyzeMatch = path.match(/^\/api\/v1\/leads\/([^/]+)\/analyze$/);
  if (leadAnalyzeMatch && method === "POST") {
    const leadId = leadAnalyzeMatch[1];
    const snapshot = ensureAnalysis(state, leadId);
    await fulfillJson(route, { lead_id: leadId, analysis: snapshot.analysis });
    return;
  }

  const leadNotesMatch = path.match(/^\/api\/v1\/leads\/([^/]+)\/notes$/);
  if (leadNotesMatch && method === "POST") {
    const leadId = leadNotesMatch[1];
    const payload = readJsonBody(route);
    state.counters.notes += 1;
    const entry: LeadActivityEntry = {
      entry_id: `note_mock_${state.counters.notes}`,
      entry_type: "note",
      actor_user_public_id: state.sessionUser.public_id,
      actor_full_name: state.sessionUser.full_name,
      created_at: nextTimestamp(state),
      from_status: null,
      to_status: null,
      note: String(payload.note ?? ""),
    };
    state.activityByLeadId[leadId] = [entry, ...(state.activityByLeadId[leadId] ?? [])];
    addAudit(state, "lead.note_added", `Added a note to lead ${leadId}.`);
    await fulfillJson(route, {
      public_id: entry.entry_id,
      note: entry.note,
      actor_user_public_id: entry.actor_user_public_id,
      actor_full_name: entry.actor_full_name,
      created_at: entry.created_at,
    });
    return;
  }

  const leadOutreachMatch = path.match(/^\/api\/v1\/leads\/([^/]+)\/outreach\/generate$/);
  if (leadOutreachMatch && method === "POST") {
    const leadId = leadOutreachMatch[1];
    const payload = readJsonBody(route);
    const draft = ensureOutreach(state, leadId, {
      tone: payload.tone as OutreachTone | undefined,
      regenerate: Boolean(payload.regenerate),
    });
    await fulfillJson(route, {
      lead_id: leadId,
      message: {
        subject: draft.subject,
        message: draft.message,
        tone: draft.tone,
      },
    });
    return;
  }

  const leadStatusMatch = path.match(/^\/api\/v1\/leads\/([^/]+)\/status$/);
  if (leadStatusMatch && method === "PATCH") {
    const leadId = leadStatusMatch[1];
    const payload = readJsonBody(route);
    const lead = getLeadOrThrow(state, leadId);
    const previousStatus = lead.status;
    lead.status = payload.status as LeadStatus;
    lead.updated_at = nextTimestamp(state);
    const historyEntry: LeadActivityEntry = {
      entry_id: `status_mock_${lead.updated_at}`,
      entry_type: "status_change",
      actor_user_public_id: state.sessionUser.public_id,
      actor_full_name: state.sessionUser.full_name,
      created_at: lead.updated_at,
      from_status: previousStatus,
      to_status: lead.status,
      note: null,
    };
    state.activityByLeadId[leadId] = [historyEntry, ...(state.activityByLeadId[leadId] ?? [])];
    const noteText =
      typeof payload.note === "string" && payload.note.trim().length > 0 ? payload.note : null;
    if (noteText) {
      state.counters.notes += 1;
      state.activityByLeadId[leadId].unshift({
        entry_id: `note_mock_${state.counters.notes}`,
        entry_type: "note",
        actor_user_public_id: state.sessionUser.public_id,
        actor_full_name: state.sessionUser.full_name,
        created_at: nextTimestamp(state),
        from_status: null,
        to_status: null,
        note: noteText,
      });
    }
    addAudit(state, "lead.status_updated", `Updated lead ${leadId} status to ${lead.status}.`);
    await fulfillJson(route, serializeLead(lead));
    return;
  }

  const leadAssignMatch = path.match(/^\/api\/v1\/leads\/([^/]+)\/assign$/);
  if (leadAssignMatch && method === "PATCH") {
    const leadId = leadAssignMatch[1];
    const payload = readJsonBody(route);
    const lead = getLeadOrThrow(state, leadId);
    lead.assigned_to_user_public_id =
      (payload.assignee_user_public_id as string | null | undefined) ?? null;
    lead.updated_at = nextTimestamp(state);
    addAudit(
      state,
      "lead.assigned",
      `Assigned lead ${leadId} to ${lead.assigned_to_user_public_id ?? "unassigned"}.`,
    );
    await fulfillJson(route, serializeLead(lead));
    return;
  }

  const leadEvidenceMatch = path.match(/^\/api\/v1\/leads\/([^/]+)\/evidence$/);
  if (leadEvidenceMatch && method === "GET") {
    const leadId = leadEvidenceMatch[1];
    await fulfillJson(route, state.evidenceByLeadId[leadId]);
    return;
  }

  const leadScoreBreakdownMatch = path.match(/^\/api\/v1\/leads\/([^/]+)\/score-breakdown$/);
  if (leadScoreBreakdownMatch && method === "GET") {
    const leadId = leadScoreBreakdownMatch[1];
    await fulfillJson(route, state.scoreBreakdownsByLeadId[leadId]);
    return;
  }

  const leadRefreshMatch = path.match(/^\/api\/v1\/leads\/([^/]+)\/refresh$/);
  if (leadRefreshMatch && method === "POST") {
    const leadId = leadRefreshMatch[1];
    const lead = getLeadOrThrow(state, leadId);
    lead.data_confidence = Number(Math.min(0.99, lead.data_confidence + 0.05).toFixed(2));
    lead.data_completeness = Number(Math.min(0.99, lead.data_completeness + 0.03).toFixed(2));
    lead.updated_at = nextTimestamp(state);
    addAudit(state, "lead.refreshed", `Refreshed provider evidence for lead ${leadId}.`);
    await fulfillJson(route, serializeLead(lead));
    return;
  }

  const leadDetailMatch = path.match(/^\/api\/v1\/leads\/([^/]+)$/);
  if (leadDetailMatch && method === "GET") {
    const lead = getLeadOrThrow(state, leadDetailMatch[1]);
    await fulfillJson(route, serializeLead(lead));
    return;
  }

  await fulfillJson(
    route,
    {
      error: {
        detail: `Unhandled E2E mock route: ${method} ${path}`,
      },
    },
    500,
  );
}

export async function installMockApi(page: Page) {
  const state = createState();

  await page.route("**/api/v1/**", async (route) => {
    await handleApiRoute(route, state);
  });

  await page.route("**/*tile.openstreetmap.org/**", async (route) => {
    await route.fulfill({ status: 204, body: "" });
  });

  return state;
}
