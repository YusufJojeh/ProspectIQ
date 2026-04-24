import { test, expect } from "./fixtures";
import { authStatePath } from "./helpers/auth";
import {
  delayApiResponseOnce,
  expectNoHorizontalOverflow,
  expectStableScreenshot,
  gotoPath,
  isDesktopWideProject,
  isMobileProject,
  isTabletProject,
  usesCompactAppNav,
} from "./helpers/page";
import { routes } from "./helpers/routes";

test.use({ storageState: authStatePath });

test("dashboard and shell render through authenticated route flow", async ({ page }, testInfo) => {
  await delayApiResponseOnce(page, /\/api\/v1\/leads/i, 800);
  await page.goto(routes.dashboard);
  await expect(page.getByText(/loading dashboard|loading workspace snapshot/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: /operational lead intelligence desk/i })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(/total leads/i)).toBeVisible();

  if (usesCompactAppNav(testInfo.project.name)) {
    await expect(page.getByRole("navigation", { name: /primary/i })).toBeVisible();
    await page.getByRole("link", { name: /jobs/i }).click();
    await expect(page).toHaveURL(/\/app\/searches$/);
  } else {
    await expect(page.getByRole("link", { name: /dashboard/i })).toBeVisible();
    await page.getByRole("link", { name: /search jobs/i }).click();
    await expect(page).toHaveURL(/\/app\/searches$/);

    await page.goto(routes.dashboard);
    await page.getByRole("button", { name: /open command menu/i }).click();
    await expect(page.getByPlaceholder(/search leads, jobs, evidence/i)).toBeVisible();
    await page.getByRole("option", { name: "Audit Logs" }).click();
    await expect(page).toHaveURL(/\/app\/audit-logs$/);
  }

  await expectNoHorizontalOverflow(page);

  if (isDesktopWideProject(testInfo.project.name)) {
    await page.goto(routes.dashboard);
    await expect(page.getByRole("heading", { name: /operational lead intelligence desk/i })).toBeVisible({
      timeout: 15_000,
    });
    await expectStableScreenshot(page.locator("main"), "dashboard-route.png");
  }

  if (isTabletProject(testInfo.project.name)) {
    await page.goto(routes.dashboard);
    await expect(page.getByRole("heading", { name: /operational lead intelligence desk/i })).toBeVisible({
      timeout: 15_000,
    });
    await expectStableScreenshot(page.locator("main"), "tablet-shell-dashboard.png");
  }

  if (isMobileProject(testInfo.project.name)) {
    await page.goto(routes.dashboard);
    await expect(page.getByRole("heading", { name: /operational lead intelligence desk/i })).toBeVisible({
      timeout: 15_000,
    });
    await expectStableScreenshot(page.locator("body"), "mobile-shell-dashboard.png");
  }
});
