import { expect, test, type Page } from "@playwright/test";

import { installMockApi } from "./support/mock-api";

async function login(page: Page) {
  await page.goto("/login");
  await expect(
    page.getByRole("heading", {
      name: /sign in to the agency lead qualification workspace/i,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: /open workspace/i }).click();
  await expect(page.getByRole("heading", { name: /lead desk snapshot/i })).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await installMockApi(page);
});

test("operator can authenticate and queue a search job from the dashboard shell", async ({
  page,
}) => {
  await login(page);

  await expect(page.getByText("Total leads")).toBeVisible();
  await expect(page.getByText("Active jobs")).toBeVisible();

  await page.getByRole("link", { name: /search jobs/i }).click();
  await expect(page.getByRole("heading", { name: /launch a scoped lead discovery run/i })).toBeVisible();

  await page.locator('input[name="business_type"]').fill("Lawyer");
  await page.locator('input[name="city"]').fill("Ankara");
  await page.locator('input[name="radius_km"]').fill("12");
  await page.locator('input[name="max_results"]').fill("20");
  await page.locator('input[name="keyword_filter"]').fill("family");
  await page.locator('select[name="website_preference"]').selectOption("must_be_missing");
  await page.getByRole("button", { name: /queue discovery job/i }).click();

  await expect(page.getByText("Lawyer")).toBeVisible();
  await expect(page.getByText("Ankara")).toBeVisible();
  await expect(page.getByText("Website missing")).toBeVisible();
  await expect(page.getByText("family")).toBeVisible();
});

test("operator can work a lead through analysis, outreach, notes, status changes, and admin settings", async ({
  page,
}) => {
  await login(page);

  await page.getByRole("link", { name: /lead workspace/i }).click();
  await expect(page.getByRole("heading", { name: /qualification workspace/i })).toBeVisible();

  await page.getByRole("button", { name: /^generate analysis$/i }).click();
  await expect(page.getByText(/analysis summary/i)).toBeVisible();
  await expect(
    page.getByText(/Acme Dental has a strong local profile/i),
  ).toBeVisible();

  await page.getByRole("button", { name: /^draft outreach$/i }).click();
  await expect(page.getByText(/Quick visibility idea for Acme Dental/i)).toBeVisible();

  await page.getByRole("link", { name: /open lead detail/i }).click();
  await expect(page.getByRole("heading", { name: /Acme Dental/i })).toBeVisible();

  await page
    .getByPlaceholder(/capture a qualification note, call outcome, or next-step context/i)
    .fill("Follow up next Tuesday afternoon.");
  await page.getByRole("button", { name: /save note/i }).click();
  await expect(page.getByText("Follow up next Tuesday afternoon.")).toBeVisible();

  await page.getByTestId("lead-detail-status-select").selectOption("qualified");
  await page
    .getByPlaceholder(/optional note to store with this status change/i)
    .fill("Qualified after checking evidence and service fit.");
  await page.getByRole("button", { name: /save status update/i }).click();
  await expect(page.getByText(/new to qualified/i)).toBeVisible();

  await expect(
    page.getByText(/Google Business Profile Optimization/i).first(),
  ).toBeVisible();
  await page
    .getByTestId("lead-detail-outreach-subject")
    .fill("Priority visibility idea for Acme Dental");
  await page.getByTestId("lead-detail-outreach-message").fill(
    "We found two local visibility fixes worth discussing this week.",
  );
  await page.getByRole("button", { name: /save edits/i }).click();
  await expect(page.getByText(/original generated draft/i)).toBeVisible();

  await page.getByRole("link", { name: /^admin$/i }).click();
  await expect(page.getByRole("heading", { name: /operational configuration/i })).toBeVisible();

  await page.locator('input[name="enrich_top_n"]').fill("25");
  await page.getByRole("button", { name: /save provider settings/i }).click();
  await expect(page.locator('input[name="enrich_top_n"]')).toHaveValue("25");

  await page.locator('textarea[name="note"]').fill("E2E scoring candidate");
  await page.getByRole("button", { name: /create scoring version/i }).click();
  await expect(page.getByText("E2E scoring candidate")).toBeVisible();
  await page.getByRole("button", { name: /^activate$/i }).click();

  await expect(page.getByText(/admin\.provider_settings_updated/i)).toBeVisible();
  await expect(page.getByText(/admin\.scoring_version_created/i)).toBeVisible();
});
