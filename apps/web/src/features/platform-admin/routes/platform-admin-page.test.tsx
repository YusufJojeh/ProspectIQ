import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AdminEntryPage, RequireRole } from "@/app/router";
import { PlatformAdminPage } from "@/features/platform-admin/routes/platform-admin-page";
import * as platformAdminApi from "@/features/platform-admin/api";
import { useAuthSession } from "@/features/auth/session";
import type {
  AdminAIUsageResponse,
  AdminFeatureHealthResponse,
  AdminInvoiceListResponse,
  AdminPlanListResponse,
  AdminProvidersResponse,
  AdminSearchJobListResponse,
  AdminSubscriptionListResponse,
  AdminUsageListResponse,
  AdminUserListResponse,
  AdminWorkspaceListResponse,
  PlatformAdminOverviewResponse,
} from "@/types/api";

vi.mock("@/features/platform-admin/api", () => ({
  disablePlatformUser: vi.fn(),
  disablePlatformWorkspace: vi.fn(),
  enablePlatformUser: vi.fn(),
  enablePlatformWorkspace: vi.fn(),
  getPlatformAiUsage: vi.fn(),
  getPlatformFeatureHealth: vi.fn(),
  getPlatformOverview: vi.fn(),
  getPlatformProviders: vi.fn(),
  getPlatformWorkspace: vi.fn(),
  listPlatformInvoices: vi.fn(),
  listPlatformPlans: vi.fn(),
  listPlatformSearchJobs: vi.fn(),
  listPlatformSubscriptions: vi.fn(),
  listPlatformUsage: vi.fn(),
  listPlatformUsers: vi.fn(),
  listPlatformWorkspaces: vi.fn(),
}));

vi.mock("@/features/auth/session", () => ({
  useAuthSession: vi.fn(),
}));

function createClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
}

function renderPlatformAdmin(path = "/app/admin") {
  return render(
    <QueryClientProvider client={createClient()}>
      <MemoryRouter initialEntries={[path]}>
        <PlatformAdminPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const overview: PlatformAdminOverviewResponse = {
  total_workspaces: 2,
  active_workspaces: 1,
  disabled_workspaces: 1,
  total_users: 4,
  active_users: 3,
  total_leads: 12,
  total_search_jobs: 5,
  failed_search_jobs: 1,
  total_ai_analyses: 7,
  total_evidence_rows: 14,
  total_icp_profiles: 2,
  total_signals: 9,
  monthly_recurring_revenue: 99,
  unpaid_invoices_count: 1,
  provider_error_count: 2,
  usage_by_metric: [{ metric_key: "searches", current_value: 10 }],
};

const emptyWorkspaces: AdminWorkspaceListResponse = { items: [] };
const emptyUsers: AdminUserListResponse = { items: [] };
const emptyPlans: AdminPlanListResponse = { items: [] };
const emptySubscriptions: AdminSubscriptionListResponse = { items: [] };
const emptyInvoices: AdminInvoiceListResponse = { items: [] };
const emptyUsage: AdminUsageListResponse = {
  items: [],
  quota_override_supported: false,
  quota_override_todo: "Quota override is not implemented.",
};
const emptyProviders: AdminProvidersResponse = {
  settings: [],
  recent_fetches: [],
  recent_errors: [],
  success_count: 0,
  failure_count: 0,
};
const emptyJobs: AdminSearchJobListResponse = { items: [] };
const emptyAiUsage: AdminAIUsageResponse = {
  analyses_count: 0,
  evidence_rows_count: 0,
  feedback_counts: [],
  latest_feedback: [],
  flagged_analyses: [],
};
const emptyFeatureHealth: AdminFeatureHealthResponse = {
  icp_profiles_count: 0,
  lead_signals_count: 0,
  scoring_versions_count: 0,
  lead_scores_count: 0,
  ai_evidence_count: 0,
  ai_feedback_count: 0,
  top_signal_types: [],
  priority_band_distribution: [],
  failed_jobs: [],
};

function mockSuccessfulApi() {
  vi.mocked(platformAdminApi.getPlatformOverview).mockResolvedValue(overview);
  vi.mocked(platformAdminApi.listPlatformWorkspaces).mockResolvedValue(emptyWorkspaces);
  vi.mocked(platformAdminApi.listPlatformUsers).mockResolvedValue(emptyUsers);
  vi.mocked(platformAdminApi.listPlatformPlans).mockResolvedValue(emptyPlans);
  vi.mocked(platformAdminApi.listPlatformSubscriptions).mockResolvedValue(
    emptySubscriptions,
  );
  vi.mocked(platformAdminApi.listPlatformInvoices).mockResolvedValue(emptyInvoices);
  vi.mocked(platformAdminApi.listPlatformUsage).mockResolvedValue(emptyUsage);
  vi.mocked(platformAdminApi.getPlatformProviders).mockResolvedValue(emptyProviders);
  vi.mocked(platformAdminApi.listPlatformSearchJobs).mockResolvedValue(emptyJobs);
  vi.mocked(platformAdminApi.getPlatformAiUsage).mockResolvedValue(emptyAiUsage);
  vi.mocked(platformAdminApi.getPlatformFeatureHealth).mockResolvedValue(
    emptyFeatureHealth,
  );
}

describe("PlatformAdminPage", () => {
  beforeEach(() => {
    mockSuccessfulApi();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders admin overview metrics from the API", async () => {
    renderPlatformAdmin();

    expect(await screen.findByText("Platform administration")).toBeInTheDocument();
    expect(screen.getAllByText("Workspaces").length).toBeGreaterThan(0);
    expect(await screen.findByText("$99")).toBeInTheDocument();
    expect(screen.getByText("Provider errors")).toBeInTheDocument();
    expect(screen.getByText("AI analyses")).toBeInTheDocument();
    expect(screen.getByText("Signals")).toBeInTheDocument();
    expect(screen.getAllByText("ICP profiles").length).toBeGreaterThan(0);
    expect(screen.getByText("Failed jobs")).toBeInTheDocument();
  });

  it("renders AI feedback and flagged analyses", async () => {
    vi.mocked(platformAdminApi.getPlatformAiUsage).mockResolvedValue({
      analyses_count: 3,
      evidence_rows_count: 5,
      feedback_counts: [{ rating: "useful", count: 2 }],
      latest_feedback: [
        {
          public_id: "afb_1",
          workspace_public_id: "ws_1",
          rating: "useful",
          correction_text: "Keep this evidence.",
          created_at: "2026-06-25T10:00:00Z",
        },
      ],
      flagged_analyses: [
        {
          public_id: "ais_1",
          workspace_public_id: "ws_1",
          workspace_name: "Acme",
          lead_public_id: "lead_1",
          lead_name: "Acme Dental",
          confidence: 0.4,
          risks_or_uncertainties: ["Website ownership is unclear."],
          created_at: "2026-06-25T09:00:00Z",
        },
      ],
    });

    renderPlatformAdmin("/app/admin/ai");

    expect(await screen.findByText("Feedback: useful")).toBeInTheDocument();
    expect(screen.getByText("Keep this evidence.")).toBeInTheDocument();
    expect(screen.getByText("Acme Dental")).toBeInTheDocument();
    expect(screen.getByText("40%")).toBeInTheDocument();
  });

  it("renders an empty state for an empty workspaces table", async () => {
    renderPlatformAdmin("/app/admin/workspaces");

    expect(await screen.findByText("No workspaces")).toBeInTheDocument();
    expect(
      screen.getByText("Workspace rows appear after accounts are created."),
    ).toBeInTheDocument();
  });

  it("renders a loading state while workspaces are pending", async () => {
    vi.mocked(platformAdminApi.listPlatformWorkspaces).mockReturnValue(
      new Promise<AdminWorkspaceListResponse>(() => undefined),
    );

    renderPlatformAdmin("/app/admin/workspaces");

    expect(await screen.findByText("Loading workspaces")).toBeInTheDocument();
    expect(
      screen
        .getAllByRole("status")
        .some((element) => element.getAttribute("aria-busy") === "true"),
    ).toBe(true);
  });

  it("renders an error state when workspaces fail to load", async () => {
    vi.mocked(platformAdminApi.listPlatformWorkspaces).mockRejectedValue(
      new Error("failed"),
    );

    renderPlatformAdmin("/app/admin/workspaces");

    expect(await screen.findByText("Workspaces unavailable")).toBeInTheDocument();
    expect(
      screen.getByText("The workspace list could not be loaded."),
    ).toBeInTheDocument();
  });

  it("re-enables a workspace action after the mutation settles", async () => {
    vi.mocked(platformAdminApi.listPlatformWorkspaces).mockResolvedValue({
      items: [
        {
          public_id: "ws_1",
          name: "Acme",
          slug: "acme",
          status: "active",
          owner_public_id: "usr_1",
          owner_email: "owner@example.com",
          users_count: 2,
          leads_count: 5,
          plan_code: "growth",
          subscription_status: "active",
          created_at: "2026-06-25T10:00:00Z",
        },
      ],
    });
    vi.mocked(platformAdminApi.disablePlatformWorkspace).mockResolvedValue({
      status: "disabled",
    });

    renderPlatformAdmin("/app/admin/workspaces");

    const action = await screen.findByRole("button", { name: "Disable" });
    fireEvent.click(action);

    await waitFor(() => {
      expect(platformAdminApi.disablePlatformWorkspace).toHaveBeenCalledWith("ws_1");
      expect(action).not.toBeDisabled();
    });
  });
});

describe("platform admin route guard", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("blocks a non-platform-admin user from platform admin routes", () => {
    vi.mocked(useAuthSession).mockReturnValue({
      session: null,
      user: {
        public_id: "usr_member",
        workspace_public_id: "ws_member",
        workspace_name: "Member Workspace",
        workspace_slug: "member-workspace",
        email: "member@example.com",
        full_name: "Member User",
        role: "member",
        status: "active",
        permissions: [],
      },
      isAuthenticated: true,
      logout: vi.fn(),
    });

    render(
      <MemoryRouter>
        <Routes>
          <Route element={<RequireRole allowedRoles={["platform_admin"]} />}>
            <Route index element={<div>Secret admin view</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.queryByText("Secret admin view")).not.toBeInTheDocument();
    expect(screen.getByText("Access restricted")).toBeInTheDocument();
  });

  it("blocks workspace owners from the SaaS admin entry route", () => {
    vi.mocked(useAuthSession).mockReturnValue({
      session: null,
      user: {
        public_id: "usr_owner",
        workspace_public_id: "ws_owner",
        workspace_name: "Owner Workspace",
        workspace_slug: "owner-workspace",
        email: "owner@example.com",
        full_name: "Owner User",
        role: "account_owner",
        status: "active",
        permissions: [],
      },
      isAuthenticated: true,
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={["/app/admin"]}>
        <AdminEntryPage />
      </MemoryRouter>,
    );

    expect(screen.getByText("Access restricted")).toBeInTheDocument();
  });
});
