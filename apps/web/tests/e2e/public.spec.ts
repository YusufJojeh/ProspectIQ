import { test, expect } from "./fixtures";
import {
  expectNoHorizontalOverflow,
  expectStableScreenshot,
  gotoPath,
  isDesktopWideProject,
  isTabletProject,
} from "./helpers/page";
import { routes } from "./helpers/routes";

test.describe.configure({ mode: "serial" });

test("landing loads, major sections render, and navigation works", async ({ page }, testInfo) => {
  await gotoPath(page, routes.home);

  await expect(page.getByText(/evidence-first/i).first()).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByRole("link", { name: "Sign in", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Request access", exact: true }).first()).toBeVisible();
  await expect(page.getByText(/discover, normalize, and score b2b leads with a deterministic pipeline/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: /from blank query to approved outreach in one governed pipeline/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /priced per seat for teams that take discovery seriously/i })).toBeVisible();

  if (isDesktopWideProject(testInfo.project.name)) {
    await expectStableScreenshot(page.locator("main"), "landing-main.png");
  }

  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: /toggle menu/i }).click();
    await page.getByRole("link", { name: "Pricing", exact: true }).click();
  } else {
    await page.getByRole("navigation").getByRole("link", { name: "Pricing", exact: true }).click();
  }
  await expect(page).toHaveURL(/#pricing$/);

  await expectNoHorizontalOverflow(page);
});

test("sign-in page validates and can open the workspace", async ({ page }, testInfo) => {
  await gotoPath(page, routes.login);

  await expect(page.getByText(/sign in to your leadscope workspace/i)).toBeVisible();
  await page.getByRole("button", { name: /open workspace/i }).click();
  await expect(page.getByText(/invalid email/i)).toBeVisible();

  await page.getByLabel(/email/i).fill("admin@prospectiq.dev");
  await page.getByLabel(/password/i).fill("ChangeMe123!");
  await page.getByRole("button", { name: /open workspace/i }).click();
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByText(/operational lead intelligence desk/i)).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("signup page creates a workspace on all breakpoints", async ({ page }) => {
  await gotoPath(page, routes.signUp);

  await expect(page.getByText(/create workspace/i).first()).toBeVisible();
  await expect(page.getByText(/create your leadscope workspace/i)).toBeVisible();

  await page.getByLabel(/full name/i).fill("Avery North");
  await page.getByLabel(/workspace name/i).fill("Northbeam Analytics");
  await page.getByLabel(/work email/i).fill("avery@northbeam.com");
  await page.getByLabel(/^password$/i).fill("LongPassword123!");
  await page.getByLabel(/confirm password/i).fill("LongPassword123!");
  await page.getByRole("button", { name: /request access/i }).click();
  await expect(page).toHaveURL(/\/app$/);
  await expectNoHorizontalOverflow(page);
});

test("signup layout remains stable on tablet", async ({ page }, testInfo) => {
  test.skip(!isTabletProject(testInfo.project.name), "Tablet-only responsive capture");
  await gotoPath(page, routes.signUp);
  await expect(page.getByText(/create your leadscope workspace/i)).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await expectStableScreenshot(page.locator("body"), "tablet-sign-up-page.png");
});

test("forgot-password page renders unavailable notice and back-to-sign-in link", async ({ page }) => {
  await gotoPath(page, routes.forgotPassword);

  await expect(page.getByText(/reset your password/i).first()).toBeVisible();
  // The page shows a notice that self-service reset is not configured
  await expect(page.getByText(/email reset not available/i)).toBeVisible();
  await expect(page.getByText(/ask your workspace administrator/i)).toBeVisible();
  // Back to sign in link is present
  await expect(page.getByRole("link", { name: /back to sign in/i })).toBeVisible();
  await expectNoHorizontalOverflow(page);
});
