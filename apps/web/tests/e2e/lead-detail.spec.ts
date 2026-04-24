import { test, expect } from "./fixtures";
import { authStatePath } from "./helpers/auth";
import { expectNoHorizontalOverflow, expectStableScreenshot, gotoPath, isDesktopWideProject } from "./helpers/page";
import { routes } from "./helpers/routes";

test.use({ storageState: authStatePath });

test("lead detail renders the imported workspace panels and survives interactions", async ({ page }, testInfo) => {
  await gotoPath(page, routes.leadDetail);

  await expect(page.getByRole("heading", { name: /acme dental/i })).toBeVisible();
  await expect(page.getByText(/normalized facts and workflow/i)).toBeVisible();
  await expect(page.getByText(/^score breakdown$/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: /evidence timeline/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /ai analysis/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /outreach workspace/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /activity timeline/i })).toBeVisible();

  await page.getByTestId("lead-analysis-generate").click();
  await expect(page.getByText(/recommended services/i)).toBeVisible();

  await page.getByTestId("lead-outreach-generate").click();
  await expect(page.getByTestId("lead-outreach-save")).toBeVisible();

  await expectNoHorizontalOverflow(page);

  if (isDesktopWideProject(testInfo.project.name)) {
    await expectStableScreenshot(page.locator("main"), "lead-detail-route.png");
  }
});
