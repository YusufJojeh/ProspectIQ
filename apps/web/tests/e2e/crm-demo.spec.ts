import fs from "node:fs/promises";
import path from "node:path";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { authStatePath } from "./helpers/auth";
import { gotoPath } from "./helpers/page";
import { routes } from "./helpers/routes";

test.use({ storageState: authStatePath });

const captureDir = path.resolve(process.cwd(), "test-results/crm-demo");

async function capture(page: Page, name: string) {
  await fs.mkdir(captureDir, { recursive: true });
  await page.screenshot({ path: path.join(captureDir, `${name}.png`), fullPage: true });
}

test("crm demo flow with local captures and no external sending", async ({ page }) => {
  const blockedRequests: string[] = [];
  page.on("request", (request) => {
    if (/\/api\/v1\/outreach\/.*\/send|smtp|gmail|hubspot|salesforce/i.test(request.url())) {
      blockedRequests.push(request.url());
    }
  });

  await gotoPath(page, "/app/crm");
  await expect(page.getByRole("heading", { name: "CRM Pipeline" })).toBeVisible();
  await expect(page.getByText("New Opportunity")).toBeVisible();
  await capture(page, "01-crm-board");

  await page.getByRole("button", { name: /create deal/i }).click();
  const createDialog = page.getByRole("dialog");
  await expect(createDialog).toBeVisible();
  await capture(page, "02-create-deal-dialog");
  await createDialog.getByRole("combobox").first().click();
  await page.getByRole("option", { name: /north clinic/i }).click();
  await createDialog.locator("#deal-title").fill("North Clinic website rebuild");
  await createDialog.locator("#deal-value").fill("6500");
  await createDialog.getByRole("button", { name: /^create deal$/i }).click();

  await expect(page.getByText("North Clinic website rebuild")).toBeVisible();
  await capture(page, "03-created-deal-card");
  await expect(page.getByRole("img", { name: /north clinic score/i })).toBeVisible();
  await capture(page, "04-lead-score-spinner-deal-card");

  await page.getByRole("combobox").filter({ hasText: "New Opportunity" }).first().click();
  await page.getByRole("option", { name: "Interested" }).click();
  await expect(page.getByText("Deal moved.")).toBeVisible();
  await capture(page, "05-moved-deal");

  await page.getByRole("link", { name: /acme dental local visibility package/i }).click();
  await expect(page.getByRole("heading", { name: /acme dental local visibility package/i })).toBeVisible();
  await capture(page, "06-deal-detail");

  await page.getByPlaceholder(/activity title/i).fill("Executive follow-up");
  await page.getByPlaceholder(/add notes/i).fill("Confirm proposal scope in the demo timeline.");
  await page.getByRole("button", { name: /add activity/i }).click();
  await expect(page.getByText("Executive follow-up")).toBeVisible();
  await capture(page, "07-activity-history");

  await page.getByRole("button", { name: /mark won/i }).click();
  await expect(page.getByText("Deal marked won.")).toBeVisible();
  await capture(page, "08-mark-won");

  await gotoPath(page, "/app/campaigns/cmp_seed_active");
  await page.getByRole("button", { name: /create deals/i }).click();
  await expect(page.getByText(/deals created/i)).toBeVisible();
  await capture(page, "09-campaign-create-deals");

  await gotoPath(page, routes.leadDetail);
  await expect(page.getByRole("link", { name: /view open deal/i })).toBeVisible();
  await capture(page, "10-lead-detail-deal-action");

  await gotoPath(page, routes.leads);
  await expect(page.getByRole("img", { name: /acme dental score/i })).toBeVisible();
  await capture(page, "11-lead-table-score-spinner");

  await gotoPath(page, "/app/crm");
  await page.getByRole("button", { name: /switch language/i }).click();
  await page.getByRole("menuitem", { name: /ar/i }).click();
  await expect(page.getByRole("heading", { name: "مسار إدارة الصفقات" })).toBeVisible();
  await capture(page, "12-arabic-crm-board");

  expect(blockedRequests).toEqual([]);
});
