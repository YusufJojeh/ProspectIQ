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

  await expect(
    page.getByRole("link", { name: "Admin", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Team", exact: true }),
  ).toHaveCount(1);
  await expect(
    page.getByRole("link", { name: "Billing", exact: true }),
  ).toHaveCount(1);

  await gotoPath(page, routes.admin);
  await expect(page.getByText(/access restricted/i)).toBeVisible();

  await gotoPath(page, routes.team);
  await expect(
    page.getByRole("heading", { name: /team users/i }),
  ).toBeVisible();
  await expect(page.getByText(/read-only access/i)).toBeVisible();
  await expect(
    page.getByRole("button", { name: /create team user/i }),
  ).toHaveCount(0);
  await expect(page.getByRole("button", { name: /save changes/i })).toHaveCount(
    0,
  );
  await expect(
    page.getByRole("button", { name: /reset password/i }),
  ).toHaveCount(0);

  await gotoPath(page, routes.billing);
  await expect(page.locator("main").getByText(/^subscription$/i)).toBeVisible();
  await expect(page.getByText(/owner action required/i)).toBeVisible();
  await expect(page.getByRole("button", { name: /apply plan/i })).toHaveCount(
    0,
  );
});

test("inactive user cannot authenticate", async ({ page }) => {
  await gotoPath(page, routes.login);

  await page.getByLabel(/email/i).fill(MOCK_IDS.inactiveEmail);
  await page.getByLabel(/password/i).fill(MOCK_IDS.inactivePassword);
  await page.getByRole("button", { name: /open workspace/i }).click();

  await expect(page.getByText(/sign-in failed/i)).toBeVisible();
  await expect(
    page.getByText(/an error occurred\. please try again\./i),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});
