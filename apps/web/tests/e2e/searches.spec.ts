import { test, expect } from "./fixtures";
import { authStatePath } from "./helpers/auth";
import { expectNoHorizontalOverflow, expectStableScreenshot, gotoPath, isDesktopWideProject } from "./helpers/page";
import { routes } from "./helpers/routes";

test.use({ storageState: authStatePath });

test("searches page supports job inspection, clone, rerun, and lead navigation", async ({ page }, testInfo) => {
  await gotoPath(page, routes.searches);

  await expect(page.getByRole("heading", { name: /scoped discovery workspace/i })).toBeVisible();
  await expect(page.getByText(/run history/i)).toBeVisible();
  await expect(page.getByText(/dentist \/ istanbul/i)).toBeVisible();

  await page.getByRole("button", { name: /^inspect$/i }).click();
  const drawer = page.getByRole("dialog", { name: /dentist in istanbul/i });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByText(/discovery settings/i)).toBeVisible();
  await drawer.getByRole("button", { name: /clone into form/i }).click();
  await drawer.getByRole("button", { name: /rerun job/i }).click();
  await expect(drawer).toContainText(/queued/i);

  await expect(page.getByTestId("search-form-business-type")).toHaveValue("Dentist");
  await expect(page.getByTestId("search-form-city")).toHaveValue("Istanbul");
  const leadsHref = await drawer.getByRole("link", { name: /view leads/i }).getAttribute("href");
  expect(leadsHref).toMatch(/search_job_id=/);
  await drawer.getByRole("link", { name: /view leads/i }).click();
  await expect(page).toHaveURL(new RegExp((leadsHref ?? "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  await expect(page.getByRole("heading", { name: /evidence-first qualification workspace/i })).toBeVisible();
  await expectNoHorizontalOverflow(page);

  if (isDesktopWideProject(testInfo.project.name)) {
    await gotoPath(page, routes.searches);
    await expect(page.getByRole("heading", { name: /scoped discovery workspace/i })).toBeVisible();
    await expectStableScreenshot(page.locator("main"), "searches-route.png");
  }
});
