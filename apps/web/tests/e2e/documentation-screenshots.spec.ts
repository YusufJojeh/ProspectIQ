import fs from "node:fs/promises";
import path from "node:path";
import type { Page } from "@playwright/test";
import { test, expect } from "./fixtures";
import { authStatePath } from "./helpers/auth";
import { gotoPath, waitForPageReady } from "./helpers/page";
import { routes } from "./helpers/routes";
test.describe.configure({ mode: "serial" });

const screenshotDir = path.resolve(
  process.cwd(),
  "../../output/playwright/frontend-figures",
);

async function ensureScreenshotDir() {
  await fs.mkdir(screenshotDir, { recursive: true });
}

async function capture(page: Page, fileName: string) {
  await waitForPageReady(page);
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(1800);
  await page.screenshot({
    path: path.join(screenshotDir, fileName),
    fullPage: true,
  });
}

async function installAssistantHistoryMocks(page: Page) {
  const sessions = new Map<
    string,
    {
      public_id: string;
      lead_id: string | null;
      title: string;
      created_at: string;
      updated_at: string;
      message_count: number;
      last_message_preview: string | null;
    }
  >();
  const messagesBySession = new Map<
    string,
    Array<{
      public_id: string;
      role: "user" | "assistant";
      content: string;
      created_at: string;
    }>
  >();
  let counter = 0;
  const nextId = (prefix: string) =>
    `${prefix}_${++counter}_${Date.now().toString(36)}`;
  const now = () => new Date().toISOString();

  function buildUiMessageStream(replyText: string) {
    const messageId = `msg_${nextId("m")}`;
    const textId = `text_${nextId("t")}`;
    const lines: string[] = [];
    const emit = (obj: unknown) =>
      lines.push(`data: ${JSON.stringify(obj)}\n\n`);
    emit({ type: "start", messageId });
    emit({ type: "text-start", id: textId });
    emit({
      type: "data-search",
      id: `search_${nextId("s")}`,
      data: { used_search: false, search_status: "not_needed", sources: [] },
    });
    emit({ type: "text-delta", id: textId, delta: replyText });
    emit({ type: "text-end", id: textId });
    emit({ type: "finish" });
    lines.push("data: [DONE]\n\n");
    return lines.join("");
  }

  await page.route("**/api/v1/assistant/chat", async (route) => {
    if (route.request().method() !== "POST") {
      await route.fallback();
      return;
    }

    const body = JSON.parse(route.request().postData() ?? "{}") as {
      messages?: Array<{
        role: string;
        parts?: Array<{ type: string; text?: string }>;
      }>;
      lead_id?: string;
      session_id?: string;
    };

    const latestUserMessage = (body.messages ?? [])
      .filter((message) => message.role === "user")
      .pop();
    const userText =
      (latestUserMessage?.parts ?? [])
        .filter((part) => part.type === "text")
        .map((part) => part.text ?? "")
        .join("\n")
        .trim() || "Untitled question";

    let sessionId = body.session_id;
    if (sessionId && !sessions.has(sessionId)) {
      sessionId = undefined;
    }
    if (!sessionId) {
      sessionId = nextId("cs");
      sessions.set(sessionId, {
        public_id: sessionId,
        lead_id: body.lead_id ?? null,
        title: userText.slice(0, 80),
        created_at: now(),
        updated_at: now(),
        message_count: 0,
        last_message_preview: null,
      });
      messagesBySession.set(sessionId, []);
    }

    const replyText = `E2E assistant reply for: ${userText}`;
    const messages = messagesBySession.get(sessionId)!;
    messages.push({
      public_id: nextId("cm"),
      role: "user",
      content: userText,
      created_at: now(),
    });
    messages.push({
      public_id: nextId("cm"),
      role: "assistant",
      content: replyText,
      created_at: now(),
    });

    const session = sessions.get(sessionId)!;
    session.message_count = messages.length;
    session.last_message_preview = replyText.slice(0, 120);
    session.updated_at = now();

    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "x-vercel-ai-ui-message-stream": "v1",
      },
      body: buildUiMessageStream(replyText),
    });
  });

  await page.route("**/api/v1/assistant/sessions**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (/\/api\/v1\/assistant\/sessions\/[^?#]+/.test(url.pathname)) {
      await route.fallback();
      return;
    }

    if (request.method() === "GET") {
      const leadFilter = url.searchParams.get("lead_id");
      const items = Array.from(sessions.values())
        .filter((session) => (leadFilter ? session.lead_id === leadFilter : true))
        .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items }),
      });
      return;
    }

    await route.fallback();
  });

  await page.route(/\/api\/v1\/assistant\/sessions\/[^?#]+/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const match = url.pathname.match(
      /\/api\/v1\/assistant\/sessions\/([^/?#]+)/,
    );
    const sessionId = match?.[1];

    if (!sessionId) {
      await route.fallback();
      return;
    }

    if (request.method() === "GET") {
      const session = sessions.get(sessionId);
      const messages = messagesBySession.get(sessionId) ?? [];
      await route.fulfill({
        status: session ? 200 : 404,
        contentType: "application/json",
        body: JSON.stringify(
          session
            ? { ...session, messages }
            : { error: { detail: "Session not found" } },
        ),
      });
      return;
    }

    if (request.method() === "DELETE") {
      sessions.delete(sessionId);
      messagesBySession.delete(sessionId);
      await route.fulfill({ status: 204, body: "" });
      return;
    }

    await route.fallback();
  });
}

test.beforeAll(async () => {
  await ensureScreenshotDir();
});

test("capture login interface screenshot", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });
  await page.route(/.*\/api\/v1\/(auth\/me|me)$/, async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "auth.invalid_token",
          detail: "Your session is invalid. Please log in again.",
        },
      }),
    });
  });
  await gotoPath(page, routes.login);
  await expect(
    page.getByLabel(/work email/i),
  ).toBeVisible();
  await page.waitForTimeout(1200);
  await capture(page, "figure-1-3-login-interface.png");
});

test.use({ storageState: authStatePath });

test("capture requested frontend figures", async ({ page }) => {
  await gotoPath(page, routes.dashboard);
  await expect(
    page.getByRole("heading", { name: /operational lead intelligence desk/i }),
  ).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(1200);
  await capture(page, "figure-2-3-user-dashboard.png");

  await gotoPath(page, routes.searches);
  await page.getByRole("button", { name: /advanced options/i }).click();
  await expect(page.getByTestId("search-form-business-type")).toBeVisible();
  await capture(page, "figure-3-3-search-task-form.png");

  await page.route("**/api/v1/search-jobs", async (route) => {
    if (route.request().method() !== "GET") {
      await route.fallback();
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            public_id: "job_running_1",
            discovery_runtime: "live",
            business_type: "Dental clinic",
            city: "Istanbul",
            region: "Kadikoy",
            radius_km: 12,
            max_results: 30,
            min_rating: 4,
            max_rating: 5,
            min_reviews: 20,
            max_reviews: 300,
            website_preference: "must_have",
            keyword_filter: "implant",
            status: "running",
            queued_at: "2026-04-03T12:00:00.000Z",
            started_at: "2026-04-03T12:01:00.000Z",
            finished_at: null,
            candidates_found: 19,
            leads_upserted: 11,
            enriched_count: 7,
            provider_error_count: 0,
          },
          {
            public_id: "job_seed_1",
            discovery_runtime: "live",
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
            queued_at: "2026-04-03T12:02:00.000Z",
            started_at: "2026-04-03T12:03:00.000Z",
            finished_at: "2026-04-03T12:07:00.000Z",
            candidates_found: 4,
            leads_upserted: 2,
            enriched_count: 2,
            provider_error_count: 0,
          },
        ],
      }),
    });
  });

  await page.route("**/api/v1/search-jobs/job_running_1/stream", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: [
        'data: {"stage":"enriching","progress":68,"message":"Collecting provider evidence and scoring matches."}',
        "",
      ].join("\n\n"),
    });
  });

  await gotoPath(page, routes.searches);
  await expect(page.getByText(/68%/i)).toBeVisible();
  await page.waitForTimeout(1200);
  await capture(page, "figure-4-3-research-progress-sse.png");

  await installAssistantHistoryMocks(page);
  await gotoPath(page, routes.assistant);
  const prompt = page.locator("textarea").first();
  await prompt.fill("Summarize the strongest outreach angle for Acme Dental.");
  await prompt.press("Enter");
  await expect(
    page.getByText(/E2E assistant reply for: Summarize the strongest outreach angle/i),
  ).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: /history/i }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.waitForTimeout(1000);
  await capture(page, "figure-5-3-messaging-and-chat.png");

  await gotoPath(page, routes.admin);
  await expect(
    page.getByText(/all systems operational|degraded service/i),
  ).toBeVisible();
  await page.waitForTimeout(1000);
  await capture(page, "figure-6-3-admin-dashboard.png");

  await gotoPath(page, routes.team);
  await expect(page.getByText(/manage users inside the current workspace only/i)).toBeVisible();
  await page.waitForTimeout(1000);
  await capture(page, "figure-7-3-team-management-page.png");

  await gotoPath(page, routes.aiAnalysis);
  await expect(page.getByText(/leads analyzed/i)).toBeVisible();
  await page.waitForTimeout(1000);
  await capture(page, "figure-8-3-smart-analysis.png");

  await gotoPath(page, routes.billing);
  await expect(page.getByText(/simulated saas billing only/i)).toBeVisible();
  await page.waitForTimeout(1000);
  await capture(page, "figure-9-3-billing-and-subscriptions.png");

  await gotoPath(page, routes.home);
  await expect(page.getByText(/evidence-first/i).first()).toBeVisible();
  await page.waitForTimeout(1200);
  await capture(page, "figure-10-3-public-storefront.png");
});
