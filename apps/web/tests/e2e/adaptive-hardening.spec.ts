import { test, expect } from "./fixtures";
import { authStatePath } from "./helpers/auth";
import { expectNoHorizontalOverflow, expectStableScreenshot, gotoPath } from "./helpers/page";
import { routes } from "./helpers/routes";

type ViewportCase = {
  name: "desktop" | "tablet" | "mobile";
  width: number;
  height: number;
};

const VIEWPORTS: ViewportCase[] = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "tablet", width: 1024, height: 1366 },
  { name: "mobile", width: 390, height: 844 },
];

const PUBLIC_ROUTES: Array<{ path: string; marker: RegExp }> = [
  { path: routes.home, marker: /evidence-first lead intelligence/i },
  { path: routes.login, marker: /sign in to your workspace/i },
  { path: routes.signUp, marker: /create your leadscope workspace/i },
  { path: routes.forgotPassword, marker: /reset your password/i },
];

const APP_ROUTES: Array<{ path: string; heading: RegExp }> = [
  { path: routes.dashboard, heading: /operational lead intelligence desk/i },
  { path: routes.searches, heading: /scoped discovery workspace/i },
  { path: routes.leads, heading: /evidence-first qualification workspace/i },
  { path: routes.leadDetail, heading: /acme dental/i },
  { path: routes.aiAnalysis, heading: /evidence-grounded recommendations/i },
  { path: routes.outreach, heading: /ai-drafted outreach messages/i },
  { path: routes.admin, heading: /workspace administration/i },
  { path: routes.auditLogs, heading: /every change, every actor/i },
  { path: routes.exports, heading: /download your lead workspace/i },
  { path: routes.settings, heading: /operational configuration/i },
];

test.describe("adaptive hardening matrix", () => {
  test("public routes remain adaptive across desktop/tablet/mobile", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "laptop", "Run adaptive matrix once on chromium laptop project.");
    test.setTimeout(300_000);

    for (const viewport of VIEWPORTS) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      for (const route of PUBLIC_ROUTES) {
        await gotoPath(page, route.path);
        await expect(page.getByText(route.marker).first()).toBeVisible({ timeout: 20_000 });
        await expectNoHorizontalOverflow(page);
      }
    }

    await page.setViewportSize({ width: 390, height: 844 });
    await gotoPath(page, routes.login);
    await expectStableScreenshot(page.locator("body"), "adaptive-public-mobile-login.png");
  });

  test.describe("authenticated routes", () => {
    test.use({ storageState: authStatePath });

    test("app routes remain adaptive across desktop/tablet/mobile", async ({ page }, testInfo) => {
      test.skip(testInfo.project.name !== "laptop", "Run adaptive matrix once on chromium laptop project.");
      test.setTimeout(300_000);

      for (const viewport of VIEWPORTS) {
        await page.setViewportSize({ width: viewport.width, height: viewport.height });
        for (const route of APP_ROUTES) {
          await gotoPath(page, route.path);
          await expect(page.getByRole("heading", { name: route.heading }).first()).toBeVisible({ timeout: 20_000 });
          await expectNoHorizontalOverflow(page);
        }
      }

      await page.setViewportSize({ width: 1440, height: 900 });
      await gotoPath(page, routes.dashboard);
      await expectStableScreenshot(page.locator("main"), "adaptive-app-desktop-dashboard.png");

      await page.setViewportSize({ width: 1024, height: 1366 });
      await gotoPath(page, routes.leads);
      await expectStableScreenshot(page.locator("main"), "adaptive-app-tablet-leads.png");

      await page.setViewportSize({ width: 390, height: 844 });
      await gotoPath(page, routes.settings);
      await expectStableScreenshot(page.locator("main"), "adaptive-app-mobile-settings.png");
    });
  });
});
