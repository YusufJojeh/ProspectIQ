import { test, expect } from "./fixtures";
import { authStatePath } from "./helpers/auth";
import { expectNoHorizontalOverflow, gotoPath } from "./helpers/page";
import { routes } from "./helpers/routes";

test.use({ storageState: authStatePath });

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("prospectiq-lang", "ar");
  });
});

test("knowledge page renders in Arabic RTL without overflow", async ({ page }) => {
  await gotoPath(page, "/app/knowledge");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByRole("heading", { name: "معرفة المبيعات", level: 1 })).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("lead detail copilot, evidence and history panels stay within the viewport in RTL", async ({ page }) => {
  await gotoPath(page, routes.leadDetail);
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByLabel(/اسأل/).first()).toBeVisible();
  await expectNoHorizontalOverflow(page);
});
