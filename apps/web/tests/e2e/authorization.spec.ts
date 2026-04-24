import { test, expect } from "./fixtures";
import { gotoPath } from "./helpers/page";
import { routes } from "./helpers/routes";
import { MOCK_IDS } from "./support/mock-api";

test.describe.configure({ mode: "serial" });

test("member cannot access admin-only governance routes", async ({ page }) => {
  await gotoPath(page, routes.login);

  await page.getByLabel(/email/i).fill(MOCK_IDS.memberEmail);
  await page.getByLabel(/password/i).fill(MOCK_IDS.memberPassword);
  await page.getByRole("button", { name: /open workspace/i }).click();
  await expect(page).toHaveURL(/\/app$/);

  await expect(page.getByRole("link", { name: "Admin", exact: true })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Team", exact: true })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Billing", exact: true })).toHaveCount(0);

  for (const path of [routes.admin, routes.team, routes.billing, routes.invoices, routes.usage, routes.settings]) {
    await gotoPath(page, path);
    await expect(page.getByText(/access restricted/i)).toBeVisible();
  }
});

test("inactive user cannot authenticate", async ({ page }) => {
  await gotoPath(page, routes.login);

  await page.getByLabel(/email/i).fill(MOCK_IDS.inactiveEmail);
  await page.getByLabel(/password/i).fill(MOCK_IDS.inactivePassword);
  await page.getByRole("button", { name: /open workspace/i }).click();

  await expect(page.getByText(/sign-in failed/i)).toBeVisible();
  await expect(page.getByText(/inactive/i)).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});
