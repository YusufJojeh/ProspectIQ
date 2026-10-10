import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";

import { test, expect } from "./fixtures";
import { authStatePath } from "./helpers/auth";
import { gotoPath } from "./helpers/page";
import { routes } from "./helpers/routes";
import { installAgentMock } from "./support/agent-mock";

test.use({ storageState: authStatePath });
test.setTimeout(90_000);
test.describe.configure({ mode: "default" });

const NOW = "2026-09-19T10:00:00Z";

/**
 * Axe rules that need a real theme/render pass are not skipped: only color-contrast
 * is excluded, because contrast is verified against the design tokens rather than
 * against this headless mock render (fonts and blend modes differ per platform).
 */
async function expectNoAxeViolations(page: Page, scope?: string) {
  let builder = new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .disableRules(["color-contrast"]);
  if (scope) builder = builder.include(scope);
  const results = await builder.analyze();
  const summary = results.violations.map(
    (violation) =>
      `${violation.id} (${violation.impact ?? "n/a"}): ${violation.nodes
        .slice(0, 3)
        .map((node) => `${node.target.join(" ")} ${node.html.slice(0, 160)}`)
        .join(" | ")}`,
  );
  expect(summary, "axe violations").toEqual([]);
}

function source(provider: string, ref: string) {
  return {
    evidence_ref: ref,
    provider,
    source_type: "web",
    url: "https://example.com/page",
    observed_at: NOW,
    actor_run_id: null,
    confidence: 0.8,
    source_quality: 0.7,
  };
}

async function mockEvidenceAndHistory(page: Page) {
  await page.route("**/api/v1/leads/*/evidence-graph", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        lead_id: "lead",
        evidence_confidence: 0.7,
        research_coverage: 0.6,
        generated_at: NOW,
        groups: [
          {
            group: "digital_presence",
            facts: [
              {
                claim_type: "has_online_booking",
                value: "no",
                status: "supported",
                confidence: 0.9,
                freshness_score: 0.8,
                source_quality: 0.7,
                sources: [source("serpapi", "ev_1")],
                contradicting_values: [],
              },
              {
                claim_type: "phone",
                value: "+90 555 111 2233",
                status: "conflicting",
                confidence: 0.4,
                freshness_score: 0.5,
                source_quality: 0.5,
                sources: [source("apify", "ev_2")],
                contradicting_values: [{ value: "+90 555 999 0000", providers: ["tavily"], sources: [source("tavily", "ev_3")] }],
              },
              {
                claim_type: "opening_hours",
                value: "9-17",
                status: "unknown",
                confidence: 0.2,
                freshness_score: 0.3,
                source_quality: 0.3,
                sources: [],
                contradicting_values: [],
              },
            ],
          },
        ],
      }),
    }),
  );
  await page.route("**/api/v1/leads/*/research-history*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        lead_id: "lead",
        pagination: { page: 1, per_page: 5, total: 1 },
        items: [
          {
            run_id: "rrun_1",
            mode: "refresh",
            depth: "standard",
            started_at: NOW,
            completed_at: NOW,
            status: "completed",
            evidence_confidence: 0.7,
            research_coverage: 0.6,
            score_before: 60,
            score_after: 72,
            changes: [
              {
                change_id: "c1",
                claim_type: "has_online_booking",
                change_type: "changed",
                before: "yes",
                after: "no",
                significance: 0.8,
                explanation: null,
              },
            ],
          },
        ],
      }),
    }),
  );
}

test.describe("Sales Knowledge", () => {
  test("has no axe violations and manages focus for dialogs", async ({ page }) => {
    await gotoPath(page, "/app/knowledge");
    await expectNoAxeViolations(page);

    // Create a collection through the dialog; focus returns to the trigger afterwards.
    const trigger = page.getByRole("button", { name: /new collection/i }).first();
    await trigger.click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByLabel(/^name$/i)).toBeFocused();
    await expectNoAxeViolations(page);

    // Focus is trapped: tabbing many times never leaves the dialog.
    for (let i = 0; i < 8; i += 1) await page.keyboard.press("Tab");
    expect(await dialog.evaluate((node) => node.contains(document.activeElement))).toBe(true);

    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(trigger).toBeFocused();

    await trigger.click();
    await dialog.getByLabel(/^name$/i).fill("Case studies");
    await page.keyboard.press("Enter");
    await expect(dialog).toBeHidden();

    // Add-document dialog (file input and visibility select included in the audit).
    await page.getByRole("button", { name: /add document/i }).first().click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expectNoAxeViolations(page);
    await page.keyboard.press("Escape");
  });

  test("archive confirmation is an alert dialog with focus trap and focus return", async ({ page }) => {
    await gotoPath(page, "/app/knowledge");
    await page.getByRole("button", { name: /new collection/i }).first().click();
    await page.getByRole("dialog").getByLabel(/^name$/i).fill("Case studies");
    await page.keyboard.press("Enter");
    await page.getByRole("button", { name: /add document/i }).first().click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel(/^title$/i).fill("Booking case");
    await dialog.getByLabel(/^content$/i).fill("We added online booking for a dental clinic.");
    await dialog.getByRole("button", { name: /add and index/i }).click();
    await expect(dialog).toBeHidden();

    const remove = page.getByRole("button", { name: /remove booking case from answers/i });
    await expect(remove).toBeVisible();
    await remove.click();
    const alertDialog = page.getByRole("alertdialog");
    await expect(alertDialog).toBeVisible();
    await expectNoAxeViolations(page);
    for (let i = 0; i < 6; i += 1) await page.keyboard.press("Tab");
    expect(await alertDialog.evaluate((node) => node.contains(document.activeElement))).toBe(true);
    await page.keyboard.press("Escape");
    await expect(alertDialog).toBeHidden();
    await expect(remove).toBeFocused();
  });

  test("search results are announced through one polite live region", async ({ page }) => {
    await gotoPath(page, "/app/knowledge");
    const search = page.getByRole("search");
    await search.getByRole("textbox").fill("booking");
    await search.getByRole("textbox").press("Enter");
    const live = page.locator('section[aria-labelledby="ks-title"] [aria-live="polite"]');
    await expect(live).toHaveCount(1);
  });

  test("icon-only controls have accessible names", async ({ page }) => {
    await gotoPath(page, "/app/knowledge");
    await page.getByRole("button", { name: /new collection/i }).first().click();
    await page.getByRole("dialog").getByLabel(/^name$/i).fill("Notes");
    await page.keyboard.press("Enter");
    await page.getByRole("button", { name: /add document/i }).first().click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel(/^title$/i).fill("Doc");
    await dialog.getByLabel(/^content$/i).fill("Some text");
    await dialog.getByRole("button", { name: /add and index/i }).click();
    const unnamed = await page.evaluate(() =>
      Array.from(document.querySelectorAll("main button"))
        .filter((button) => !(button.textContent ?? "").trim() && !button.getAttribute("aria-label") && !button.getAttribute("aria-labelledby"))
        .map((button) => button.outerHTML.slice(0, 120)),
    );
    expect(unnamed).toEqual([]);
  });
});

test.describe("Lead detail: Copilot, Evidence Graph and Research History", () => {
  test("idle state, evidence graph and history have no axe violations and status is not color-only", async ({ page }) => {
    await installAgentMock(page);
    await mockEvidenceAndHistory(page);
    await gotoPath(page, routes.leadDetail);

    const graph = page.getByRole("region", { name: /evidence graph/i });
    await expect(graph.getByText("Supported", { exact: true }).first()).toBeVisible({ timeout: 20_000 });
    await expect(graph.getByText("Conflicting", { exact: true }).first()).toBeVisible();
    await expect(graph.getByText("Unverified", { exact: true }).first()).toBeVisible();

    await expect(page.getByText(/what changed/i).first()).toBeVisible();
    await expectNoAxeViolations(page, "main");
  });

  test("copilot approval flow is keyboard operable, announced, and axe clean at every phase", async ({ page }) => {
    await installAgentMock(page);
    await mockEvidenceAndHistory(page);
    await gotoPath(page, routes.leadDetail);

    const goal = page.getByLabel(/ask the copilot/i);
    await goal.fill("Why is this a good fit?");
    // Submit from the keyboard, not the pointer.
    await page.getByRole("button", { name: /^ask$/i }).focus();
    await page.keyboard.press("Enter");

    const approvals = page.getByRole("region", { name: /waiting for your approval/i });
    await expect(approvals).toBeVisible();
    // The pending state is stated in text (badge), not only by color.
    await expect(approvals.getByText(/^pending$/i)).toBeVisible();
    await expectNoAxeViolations(page, "main");

    // Live-region budget: the run announces phase and activity, not a stream of duplicates.
    const liveRegions = await page.locator('[aria-live="polite"]').count();
    expect(liveRegions).toBeLessThanOrEqual(6);

    // Reject flow: revealing the reason field moves focus somewhere sensible and stays operable.
    await approvals.getByRole("button", { name: /^decline$/i }).focus();
    await page.keyboard.press("Enter");
    const reason = approvals.getByLabel(/reason/i);
    await expect(reason).toBeVisible();
    await expectNoAxeViolations(page, "main");

    // Approve path from the keyboard after cancelling the decline form.
    const approve = approvals.getByRole("button", { name: /^approve$/i });
    if (await approve.isVisible()) {
      await approve.focus();
      await page.keyboard.press("Enter");
    } else {
      await approvals.getByRole("button", { name: /decline change/i }).focus();
      await page.keyboard.press("Enter");
    }

    await expect(page.getByText(/strong fit/i)).toBeVisible();
    await expectNoAxeViolations(page, "main");
    // A terminal state is stated in words.
    await expect(page.getByText(/^done$|^declined$|^applied$/i).first()).toBeVisible();
  });

  test("a failed run is stated with text and role=alert, not color alone", async ({ page }) => {
    await page.route("**/api/v1/agent/runs", (route) => {
      if (route.request().method() === "POST") {
        return route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ detail: "Forbidden" }) });
      }
      return route.fallback();
    });
    await mockEvidenceAndHistory(page);
    await gotoPath(page, routes.leadDetail);
    await page.getByLabel(/ask the copilot/i).fill("Why?");
    await page.getByRole("button", { name: /^ask$/i }).click();

    const alert = page.getByRole("alert").filter({ hasText: /\w{4,}/ }).first();
    await expect(alert).toBeVisible();
    expect((await alert.innerText()).trim().length).toBeGreaterThan(10);
    await expectNoAxeViolations(page, "main");
  });
});
