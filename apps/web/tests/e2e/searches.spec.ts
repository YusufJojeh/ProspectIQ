import { test, expect } from "./fixtures";
import { authStatePath } from "./helpers/auth";
import { expectNoHorizontalOverflow, expectStableScreenshot, gotoPath, isDesktopWideProject } from "./helpers/page";
import { routes } from "./helpers/routes";
import { MOCK_IDS } from "./support/mock-api";

test.use({ storageState: authStatePath });

test("searches page supports job inspection, clone, rerun, and lead navigation", async ({ page }, testInfo) => {
  await gotoPath(page, routes.searches);

  await expect(page.getByRole("heading", { name: /scoped discovery workspace/i })).toBeVisible();
  await expect(page.getByText(/run history/i)).toBeVisible();
  await expect(page.getByText(/dentist \/ istanbul/i)).toBeVisible();

  await page.getByRole("button", { name: /^inspect$/i }).click();
  await expect(page.getByRole("heading", { name: /dentist in istanbul/i })).toBeVisible();
  await expect(page.getByText(/discovery settings/i)).toBeVisible();
  await page.getByRole("button", { name: /clone into form/i }).click();
  await page.getByRole("button", { name: /close/i }).click();

  await expect(page.getByTestId("search-form-business-type")).toHaveValue("Dentist");
  await expect(page.getByTestId("search-form-city")).toHaveValue("Istanbul");

  await page.getByRole("button", { name: /rerun job/i }).click();
  await expect(page.getByText(/queued/i).first()).toBeVisible();

  await page.getByRole("link", { name: /view leads/i }).click();
  await expect(page).toHaveURL(new RegExp(`search_job_id=${MOCK_IDS.seedJobId}`));
  await expect(page.getByRole("heading", { name: /evidence-first qualification workspace/i })).toBeVisible();
  await expectNoHorizontalOverflow(page);

  if (isDesktopWideProject(testInfo.project.name)) {
    await gotoPath(page, routes.searches);
    await expect(page.getByRole("heading", { name: /scoped discovery workspace/i })).toBeVisible();
    await expectStableScreenshot(page.locator("main"), "searches-route.png");
  }
});
