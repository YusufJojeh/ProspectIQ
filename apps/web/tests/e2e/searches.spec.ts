import { test, expect } from "./fixtures";
import { authStatePath } from "./helpers/auth";
import {
  expectNoHorizontalOverflow,
  expectStableScreenshot,
  gotoPath,
  isDesktopWideProject,
} from "./helpers/page";
import { routes } from "./helpers/routes";

test.use({ storageState: authStatePath });

test("searches page shows AI prompt input as the primary entry point with structured form collapsed", async ({
  page,
}) => {
  await gotoPath(page, routes.searches);

  // Part 2: NLP textarea should be visible at the top of the create-job card
  const promptTextarea = page.getByPlaceholder(
    /Describe what you're looking for/i,
  );
  await expect(promptTextarea).toBeVisible();

  // Primary CTA is "Search with AI"
  await expect(
    page.getByRole("button", { name: /Search with AI/i }),
  ).toBeVisible();

  // Structured form is hidden behind the "Advanced options" collapsible — its
  // required field (business type input) should NOT be visible by default.
  await expect(page.getByTestId("search-form-business-type")).toBeHidden();

  // Click the "Advanced options" collapsible trigger → form becomes visible
  await page.getByRole("button", { name: /Advanced options/i }).click();
  await expect(page.getByTestId("search-form-business-type")).toBeVisible();
  await expect(page.getByTestId("search-form-city")).toBeVisible();
});

test("Part 6: search-job cards do not render raw i18n placeholders", async ({
  page,
}) => {
  await gotoPath(page, routes.searches);
  await expect(page.getByText(/run history/i)).toBeVisible();

  // jobCardSummary template used to be "{{businessType}} in {{city}}" with wrong
  // variables passed → rendered raw {{placeholders}}. Verify that's fixed.
  const mainBody = page.locator("main");
  await expect(mainBody).not.toContainText("{{");
  await expect(mainBody).not.toContainText("}}");
});

test("searches page supports job inspection, clone, rerun, and lead navigation", async ({
  page,
}, testInfo) => {
  await gotoPath(page, routes.searches);

  await expect(
    page.getByRole("heading", { name: /scoped discovery workspace/i }),
  ).toBeVisible();
  await expect(page.getByText(/run history/i)).toBeVisible();
  await expect(page.getByText(/dentist \/ istanbul/i)).toBeVisible();

  await page.getByRole("button", { name: /^inspect$/i }).click();
  const drawer = page.getByRole("dialog", { name: /dentist in istanbul/i });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByText(/discovery settings/i)).toBeVisible();
  await drawer.getByRole("button", { name: /clone into form/i }).click();
  await drawer.getByRole("button", { name: /rerun job/i }).click();
  await expect(drawer).toContainText(/queued/i);

  await expect(page.getByTestId("search-form-business-type")).toHaveValue(
    "Dentist",
  );
  await expect(page.getByTestId("search-form-city")).toHaveValue("Istanbul");
  const leadsHref = await drawer
    .getByRole("link", { name: /view leads/i })
    .getAttribute("href");
  expect(leadsHref).toMatch(/search_job_id=/);
  await drawer.getByRole("link", { name: /view leads/i }).click();
  await expect(page).toHaveURL(
    new RegExp((leadsHref ?? "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&")),
  );
  await expect(
    page.getByRole("heading", {
      name: /evidence-first qualification workspace/i,
    }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);

  if (isDesktopWideProject(testInfo.project.name)) {
    await gotoPath(page, routes.searches);
    await expect(
      page.getByRole("heading", { name: /scoped discovery workspace/i }),
    ).toBeVisible();
    await expectStableScreenshot(page.locator("main"), "searches-route.png");
  }
});
