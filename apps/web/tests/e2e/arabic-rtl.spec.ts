import { test, expect } from "./fixtures";
import { authStatePath } from "./helpers/auth";
import { expectNoHorizontalOverflow, gotoPath, isMobileProject } from "./helpers/page";
import { routes } from "./helpers/routes";

test.use({ storageState: authStatePath });

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("prospectiq-lang", "ar");
  });
});

async function expectArabicDocument(page: Parameters<typeof expectNoHorizontalOverflow>[0]) {
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("lang", /ar/);
  await expectNoHorizontalOverflow(page);
}

test("Arabic RTL shell and dashboard render without layout overflow", async ({ page }, testInfo) => {
  await gotoPath(page, routes.dashboard);

  await expect(page.getByRole("heading", { name: /مكتب ذكاء العملاء التشغيلي/i })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(/إجمالي العملاء/i)).toBeVisible();
  await expectArabicDocument(page);

  if (isMobileProject(testInfo.project.name)) {
    const mobileNav = page.getByRole("navigation", { name: /primary/i });
    await expect(mobileNav).toBeVisible();
    await expect(mobileNav.getByRole("link", { name: /العملاء المحتملون/i })).toBeVisible();
  }
});

test("Arabic RTL AI, leads, detail, and settings routes stay usable", async ({ page }) => {
  await gotoPath(page, routes.aiAnalysis);
  await expect(page.getByRole("heading", { name: /توصيات مبنية على الأدلة/i })).toBeVisible({
    timeout: 15_000,
  });
  await expectArabicDocument(page);

  for (const route of [routes.leads, routes.leadDetail, routes.settings, routes.admin]) {
    await gotoPath(page, route);
    await expectArabicDocument(page);
  }
});
