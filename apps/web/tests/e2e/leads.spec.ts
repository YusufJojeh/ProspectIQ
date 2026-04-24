import { test, expect } from "./fixtures";
import { authStatePath } from "./helpers/auth";
import { expectNoHorizontalOverflow, expectStableScreenshot, gotoPath, isDesktopWideProject } from "./helpers/page";
import { routes } from "./helpers/routes";

test.use({ storageState: authStatePath });

test("leads explorer supports filters, view toggles, selection, export, and empty state", async ({ page }, testInfo) => {
  await gotoPath(page, routes.leads);

  await expect(page.getByRole("heading", { name: /evidence-first qualification workspace/i })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByRole("heading", { name: "Filter rail" })).toBeVisible();
  await expect(page.getByText(/live workspace/i)).toBeVisible();

  await page.getByRole("button", { name: /cards/i }).click();
  await expect(page.getByText(/north clinic/i)).toBeVisible();

  await page.getByRole("button", { name: /map/i }).click();
  await expect(page.locator(".leaflet-container")).toBeVisible();

  await page.getByRole("button", { name: /table/i }).click();
  await page.getByRole("button", { name: /acme dental/i }).getByRole("checkbox").click();
  await expect(page.getByText(/1 selected/i)).toBeVisible();

  await page.getByPlaceholder(/company, city, or domain/i).fill("zzzz-no-match");
  await expect(page.getByText(/no leads match the current filters/i)).toBeVisible();

  await page.getByRole("button", { name: /reset/i }).click();
  await expect(page.getByRole("button", { name: /acme dental/i })).toBeVisible();

  await page.getByRole("button", { name: /acme dental/i }).getByRole("checkbox").click();
  await page.getByRole("button", { name: /export 1/i }).click();
  await expect(page.getByText(/export started/i)).toBeVisible();

  await expectNoHorizontalOverflow(page);

  if (isDesktopWideProject(testInfo.project.name)) {
    await expectStableScreenshot(page.locator("main"), "leads-route.png");
  }
});
