import fs from "node:fs/promises";
import path from "node:path";
import type { Page } from "@playwright/test";
import { test, expect } from "./fixtures";
import { authStatePath } from "./helpers/auth";
import { gotoPath } from "./helpers/page";
import { routes } from "./helpers/routes";

test.use({ storageState: authStatePath });

const captureDir = path.resolve(process.cwd(), "test-results/campaign-demo");

async function capture(page: Page, name: string) {
  await fs.mkdir(captureDir, { recursive: true });
  await page.screenshot({ path: path.join(captureDir, `${name}.png`), fullPage: true });
}

test("campaign demo closeout flow with local captures and no sending", async ({ page }) => {
  const sendRequests: string[] = [];
  page.on("request", (request) => {
    if (/\/api\/v1\/outreach\/.*\/send/.test(request.url())) {
      sendRequests.push(request.url());
    }
  });

  await gotoPath(page, "/app/campaigns");
  await expect(page.getByRole("heading", { name: "Campaigns" })).toBeVisible();
  await capture(page, "01-campaign-list");

  await page.getByRole("button", { name: /create campaign/i }).click();
  const createDialog = page.getByRole("dialog");
  await expect(createDialog).toBeVisible();
  await capture(page, "02-create-campaign-dialog");
  await createDialog.locator("input").fill("Campaign demo closeout");
  await createDialog
    .locator("textarea")
    .fill("Playwright-created campaign for closeout verification.");
  await createDialog.getByRole("button", { name: /^create campaign$/i }).click();

  await expect(page.getByText("Campaign demo closeout")).toBeVisible();
  await page.getByRole("link", { name: /open campaign/i }).first().click();
  await expect(page.getByRole("tab", { name: /leads/i })).toBeVisible();
  await capture(page, "03-campaign-detail-overview");

  await page.getByRole("combobox").click();
  await page.getByRole("option", { name: /acme dental/i }).click();
  await page.getByRole("button", { name: /^add lead$/i }).click();
  await expect(page.getByRole("link", { name: /acme dental/i })).toBeVisible();
  await capture(page, "04-campaign-leads-section");
  await expect(page.getByRole("img", { name: /acme dental score/i })).toBeVisible();
  await capture(page, "05-lead-score-spinner-campaign");

  await page.getByRole("tab", { name: /sequence/i }).click();
  await expect(page.getByText(/no sequence steps/i)).toBeVisible();
  await capture(page, "06-sequence-empty-state");
  await page.getByRole("button", { name: /generate sequence/i }).click();
  await expect(page.getByText(/step 3/i)).toBeVisible();
  await capture(page, "07-generated-sequence");

  await page.getByRole("tab", { name: /drafts/i }).click();
  await page.getByRole("button", { name: /generate drafts/i }).click();
  await expect(page.getByText(/quick visibility idea/i)).toBeVisible();
  await capture(page, "08-generated-drafts");

  await page.getByRole("tab", { name: /events/i }).click();
  await expect(page.getByText(/draft generated/i)).toBeVisible();
  await capture(page, "09-outreach-events-history");

  await gotoPath(page, routes.leadDetail);
  await expect(page.getByText(/add to campaign/i)).toBeVisible();
  await capture(page, "10-lead-detail-add-to-campaign");

  await gotoPath(page, routes.leads);
  await expect(page.getByRole("img", { name: /acme dental score/i })).toBeVisible();
  await capture(page, "11-lead-table-score-spinner");

  await gotoPath(page, "/app/campaigns");
  await page.getByRole("button", { name: /switch language/i }).click();
  await page.getByRole("menuitem", { name: /ar العربية/i }).click();
  await expect(page.getByRole("heading", { name: "الحملات" })).toBeVisible();
  await capture(page, "12-arabic-campaign-page");

  expect(sendRequests).toEqual([]);
});
