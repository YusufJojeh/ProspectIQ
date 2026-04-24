import { test, expect } from "./fixtures";
import { authStatePath } from "./helpers/auth";
import {
  expectNoHorizontalOverflow,
  expectStableScreenshot,
  gotoPath,
  isDesktopWideProject,
  isMobileProject,
} from "./helpers/page";
import { routes } from "./helpers/routes";

test.use({ storageState: authStatePath });
test.describe.configure({ mode: "serial" });

const governanceRoutes = [
  {
    path: routes.aiAnalysis,
    heading: /evidence-grounded recommendations/i,
    headingSelector: "text",
  },
  {
    path: routes.outreach,
    heading: /ai-drafted outreach messages/i,
    headingSelector: "text",
  },
  {
    path: routes.admin,
    heading: /workspace administration/i,
    headingSelector: "text",
  },
  {
    path: routes.team,
    heading: /team users/i,
    headingSelector: "text",
  },
  {
    path: routes.billing,
    heading: /subscription/i,
    headingSelector: "text",
  },
  {
    path: routes.invoices,
    heading: /invoices/i,
    headingSelector: "text",
  },
  {
    path: routes.usage,
    heading: /usage and plan limits/i,
    headingSelector: "text",
  },
  {
    path: routes.auditLogs,
    heading: /every change, every actor/i,
    headingSelector: "text",
  },
  {
    path: routes.exports,
    heading: /download your lead workspace/i,
    headingSelector: "text",
  },
  {
    path: routes.settings,
    heading: /operational configuration/i,
    headingSelector: "text",
  },
] as const;

for (const route of governanceRoutes) {
  test(`governance route ${route.path} loads and stays structurally stable`, async ({ page }, testInfo) => {
    await gotoPath(page, route.path);

    const headingLocator =
      route.headingSelector === "role" ? page.getByRole("heading", { name: route.heading }) : page.getByText(route.heading).first();
    await expect(headingLocator).toBeVisible({ timeout: 15_000 });
    if (route.path === routes.aiAnalysis) {
      await expect(page.getByText(/leads analyzed/i)).toBeVisible();
    } else if (route.path === routes.outreach) {
      await expect(page.getByText(/leads available/i)).toBeVisible();
    } else if (route.path === routes.admin) {
      await expect(page.getByText(/all systems operational|degraded service/i)).toBeVisible();
    } else if (route.path === routes.team) {
      await expect(page.getByText(/manage users inside the current workspace only/i)).toBeVisible();
    } else if (route.path === routes.billing) {
      await expect(page.getByText(/simulated saas billing only/i)).toBeVisible();
    } else if (route.path === routes.invoices) {
      await expect(page.getByText(/internal invoice and payment-attempt records/i)).toBeVisible();
    } else if (route.path === routes.usage) {
      await expect(page.getByText(/usage is scoped to the current workspace/i)).toBeVisible();
    } else if (route.path === routes.auditLogs) {
      await expect(page.getByText(/\d+ \/ \d+ events/i)).toBeVisible();
    } else if (route.path === routes.exports) {
      await expect(page.getByText(/preview/i)).toBeVisible();
    } else if (route.path === routes.settings) {
      await expect(page.getByText(/system overview/i)).toBeVisible();
    }
    await expectNoHorizontalOverflow(page);

    if (isMobileProject(testInfo.project.name) && route.path === routes.settings) {
      await expectStableScreenshot(page.locator("main"), "mobile-settings-route.png");
    }
  });
}
