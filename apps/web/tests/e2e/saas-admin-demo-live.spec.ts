import fs from "node:fs/promises";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const screenshotDir = path.resolve(process.cwd(), "test-results/saas-admin-demo");
const apiURL = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";

const credentials = {
  platform: {
    email: "platform-admin@example.test",
    password: "PlatformAdmin123!",
  },
  owner: {
    email: "admin@example.test",
    password: "AdminPass123!",
  },
  member: {
    email: "user1@example.test",
    password: "UserPass123!",
  },
};

type AuthenticatedUser = {
  role: string;
  email: string;
};

type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthenticatedUser;
};

type ListResponse<T> = {
  items: T[];
};

type WorkspaceSummary = {
  public_id: string;
  name: string;
  status: string;
};

type UserSummary = {
  public_id: string;
  email: string;
  status: string;
};

type LeadSummary = {
  public_id: string;
  company_name: string;
  signals_count: number;
  latest_score: number | null;
};

type SearchJobSummary = {
  public_id: string;
  status: string;
};

async function ensureScreenshotDir() {
  await fs.mkdir(screenshotDir, { recursive: true });
}

async function capture(page: Page, fileName: string) {
  await page.waitForLoadState("domcontentloaded");
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(600);
  await page.screenshot({
    path: path.join(screenshotDir, fileName),
    fullPage: true,
  });
}

async function clearBrowserSession(page: Page) {
  await page.goto("/");
  await page.evaluate(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.dispatchEvent(new CustomEvent("prospectiq:auth-session"));
  });
}

async function loginThroughUi(
  page: Page,
  email: string,
  password: string,
  expectedUrl: RegExp = /\/app/,
) {
  await clearBrowserSession(page);
  await page.goto("/login");
  await page.getByLabel(/work email/i).fill(email);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole("button", { name: /open workspace/i }).click();
  await expect(page).toHaveURL(expectedUrl);
}

async function apiLogin(
  request: APIRequestContext,
  email: string,
  password: string,
): Promise<TokenResponse> {
  const response = await request.post(`${apiURL}/api/v1/auth/login`, {
    data: { email, password },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as TokenResponse;
}

async function apiGet<T>(
  request: APIRequestContext,
  token: string,
  pathName: string,
): Promise<T> {
  const response = await request.get(`${apiURL}${pathName}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as T;
}

async function gotoAndExpect(page: Page, pathName: string, text: RegExp | string) {
  await page.goto(pathName);
  await expect(page.getByText(text).first()).toBeVisible({ timeout: 15_000 });
}

test.describe.configure({ mode: "serial" });

test.beforeAll(async () => {
  await ensureScreenshotDir();
});

test("captures SaaS platform admin demo against seeded live data", async ({
  page,
  request,
}) => {
  test.setTimeout(300_000);

  await clearBrowserSession(page);
  await page.goto("/login");
  await expect(page.getByLabel(/work email/i)).toBeVisible();
  await capture(page, "01-login-page.png");

  const platformToken = (
    await apiLogin(request, credentials.platform.email, credentials.platform.password)
  ).access_token;
  const ownerToken = (
    await apiLogin(request, credentials.owner.email, credentials.owner.password)
  ).access_token;

  const workspaces = await apiGet<ListResponse<WorkspaceSummary>>(
    request,
    platformToken,
    "/api/v1/admin/workspaces",
  );
  const activeWorkspace =
    workspaces.items.find((workspace) => workspace.public_id === "ws_default") ??
    workspaces.items.find((workspace) => workspace.status === "active");
  expect(activeWorkspace).toBeTruthy();

  const users = await apiGet<ListResponse<UserSummary>>(
    request,
    platformToken,
    "/api/v1/admin/users",
  );
  const memberUser = users.items.find((user) => user.email === credentials.member.email);
  expect(memberUser).toBeTruthy();

  const leads = await apiGet<ListResponse<LeadSummary>>(
    request,
    ownerToken,
    "/api/v1/leads?page_size=50&sort=score_desc",
  );
  const detailLead =
    leads.items.find((lead) => lead.signals_count > 0 && lead.latest_score !== null) ??
    leads.items[0];
  expect(detailLead).toBeTruthy();

  const jobs = await apiGet<ListResponse<SearchJobSummary>>(
    request,
    ownerToken,
    "/api/v1/search-jobs",
  );
  const job = jobs.items[0];
  expect(job).toBeTruthy();

  await loginThroughUi(page, credentials.platform.email, credentials.platform.password);
  await expect(page.getByRole("link", { name: /admin/i })).toBeVisible({
    timeout: 15_000,
  });
  await capture(page, "02-platform-admin-login-success.png");

  await gotoAndExpect(page, "/app/admin", /Platform administration/i);
  await capture(page, "03-admin-overview-dashboard.png");

  await gotoAndExpect(page, "/app/admin/workspaces", /Workspaces/i);
  await expect(page.getByText(activeWorkspace!.public_id).or(page.getByText(activeWorkspace!.name))).toBeVisible();
  await capture(page, "04-admin-workspaces.png");

  await gotoAndExpect(
    page,
    `/app/admin/workspaces/${activeWorkspace!.public_id}`,
    /Feature summary|Profile and feature summary/i,
  );
  await capture(page, "05-admin-workspace-detail.png");

  await gotoAndExpect(page, "/app/admin/workspaces", /Workspaces/i);
  const activeWorkspaceRow = page
    .getByRole("row")
    .filter({ hasText: activeWorkspace!.name })
    .first();
  await activeWorkspaceRow.getByRole("button", { name: /disable/i }).click();
  await expect(activeWorkspaceRow.getByText(/disabled/i)).toBeVisible({
    timeout: 15_000,
  });
  await capture(page, "06-disable-workspace-action.png");

  const blockedBearer = await request.get(`${apiURL}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
  });
  expect(blockedBearer.status()).toBe(401);

  await clearBrowserSession(page);
  await page.goto("/login");
  await page.getByLabel(/work email/i).fill(credentials.owner.email);
  await page.getByLabel(/password/i).fill(credentials.owner.password);
  await page.getByRole("button", { name: /open workspace/i }).click();
  await expect(page.getByText("Sign-in failed")).toBeVisible({
    timeout: 15_000,
  });
  await capture(page, "07-disabled-workspace-access-rejection.png");

  await loginThroughUi(page, credentials.platform.email, credentials.platform.password);
  await gotoAndExpect(page, "/app/admin/workspaces", /Workspaces/i);
  const disabledWorkspaceRow = page
    .getByRole("row")
    .filter({ hasText: activeWorkspace!.name })
    .first();
  await disabledWorkspaceRow.getByRole("button", { name: /enable/i }).click();
  await expect(disabledWorkspaceRow.getByText(/active/i)).toBeVisible({
    timeout: 15_000,
  });
  await capture(page, "08-re-enable-workspace-action.png");

  await gotoAndExpect(page, "/app/admin/users", /Users/i);
  await capture(page, "09-admin-users.png");

  const memberRow = page.getByRole("row").filter({ hasText: credentials.member.email }).first();
  await memberRow.getByRole("button", { name: /disable/i }).click();
  await expect(memberRow.getByText(/inactive/i)).toBeVisible({ timeout: 15_000 });
  await capture(page, "10-disable-user-action.png");

  await memberRow.getByRole("button", { name: /enable/i }).click();
  await expect(memberRow.getByText(/active/i)).toBeVisible({ timeout: 15_000 });
  await capture(page, "11-re-enable-user-action.png");

  await gotoAndExpect(page, "/app/admin/billing", /Payment attempts|Invoices/i);
  await capture(page, "12-admin-billing.png");

  await gotoAndExpect(page, "/app/admin/usage", /Usage counters/i);
  await capture(page, "13-admin-usage.png");

  await gotoAndExpect(page, "/app/admin/providers", /Provider health/i);
  await capture(page, "14-admin-providers.png");

  await gotoAndExpect(page, "/app/admin/jobs", /Search jobs/i);
  await capture(page, "15-admin-jobs.png");

  await gotoAndExpect(page, "/app/admin/ai", /AI usage/i);
  await capture(page, "16-admin-ai.png");

  await loginThroughUi(page, credentials.owner.email, credentials.owner.password);
  await page.goto("/app/admin");
  await expect(page.getByText(/access restricted/i)).toBeVisible({ timeout: 15_000 });
  await capture(page, "17-owner-blocked-from-platform-admin.png");

  await gotoAndExpect(page, "/app/workspace-admin", /Workspace administration/i);
  await capture(page, "18-owner-workspace-admin.png");

  await gotoAndExpect(page, "/app/settings", /ICP profiles/i);
  await page.getByRole("tab", { name: /ICP profiles/i }).click();
  await expect(page.getByText(/Workspace ICP profiles/i)).toBeVisible({
    timeout: 15_000,
  });
  await capture(page, "19-icp-profiles-settings-tab.png");

  await gotoAndExpect(page, "/app/leads", /Live workspace/i);
  await expect(page.getByText(/Top signal|Priority score|ICP fit/i).first()).toBeVisible({
    timeout: 15_000,
  });
  await capture(page, "20-leads-table-signals-scores-icp.png");

  await gotoAndExpect(
    page,
    `/app/leads/${detailLead!.public_id}`,
    new RegExp(detailLead!.company_name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i"),
  );
  await page.getByText("Lead signals", { exact: true }).first().scrollIntoViewIfNeeded();
  await capture(page, "21-lead-detail-signals-panel.png");

  await page.getByText("Scoring 2.0", { exact: true }).first().scrollIntoViewIfNeeded();
  await capture(page, "22-lead-detail-scoring-v2-panel.png");

  await page.getByText("ICP match", { exact: true }).first().scrollIntoViewIfNeeded();
  await capture(page, "23-lead-detail-icp-match-panel.png");

  await page.getByText("Evidence used by AI", { exact: true }).first().scrollIntoViewIfNeeded();
  await capture(page, "24-lead-detail-ai-evidence-panel.png");

  await page.getByText(/outreach/i).first().scrollIntoViewIfNeeded();
  await capture(page, "25-lead-detail-outreach-draft-status.png");

  await gotoAndExpect(page, "/app/searches", /Create new job/i);
  await capture(page, "26-search-job-creation-page.png");

  await gotoAndExpect(
    page,
    `/app/searches/jobs/${job!.public_id}`,
    /Discovery run|Search job|Run/i,
  );
  await capture(page, "27-search-job-detail-progress.png");
});
