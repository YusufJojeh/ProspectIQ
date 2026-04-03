import { expect, test, type Page } from "@playwright/test";
import { installMockApi } from "./support/mock-api";

async function assertNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() =>
    Math.max(0, document.documentElement.scrollWidth - window.innerWidth),
  );
  expect(overflow).toBeLessThanOrEqual(1);
}

async function attachScreenshot(page: Page, name: string) {
  await test.info().attach(name, {
    body: await page.screenshot({ fullPage: true, animations: "disabled" }),
    contentType: "image/png",
  });
}

async function login(page: Page) {
  await page.goto("/login");
  await page.getByRole("button", { name: /open workspace/i }).click();
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByRole("heading", { name: /lead desk snapshot/i })).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await installMockApi(page);
  await page.emulateMedia({ reducedMotion: "reduce" });
});

for (const viewport of [
  { name: "desktop", size: { width: 1440, height: 1600 } },
  { name: "tablet", size: { width: 1024, height: 1500 } },
  { name: "mobile", size: { width: 390, height: 1400 } },
]) {
  test(`homepage layout is stable on ${viewport.name}`, async ({ page }) => {
    await page.setViewportSize(viewport.size);
    await page.goto("/");

    await expect(
      page.getByRole("heading", {
        name: /turn local search evidence into qualified outreach you can defend/i,
      }),
    ).toBeVisible();
    await expect(
      page.getByAltText(/LeadScope AI hero illustration showing layered 3D analytics panels/i),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", {
        name: /the home page says exactly what the product does under the hood/i,
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", {
        name: /open the lead desk and move from discovery to qualification in one pass/i,
      }),
    ).toBeVisible();

    const heroImageWidth = await page
      .getByAltText(/LeadScope AI hero illustration showing layered 3D analytics panels/i)
      .evaluate((element) => (element as HTMLImageElement).naturalWidth);
    expect(heroImageWidth).toBeGreaterThan(1000);

    await assertNoHorizontalOverflow(page);
    await attachScreenshot(page, `homepage-${viewport.name}`);
  });
}

test("login page remains readable on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 1100 });
  await page.goto("/login");

  await expect(
    page.getByRole("heading", { name: /sign in to the agency lead qualification workspace/i }),
  ).toBeVisible();
  await expect(page.getByLabel(/workspace/i)).toBeVisible();
  await expect(page.getByLabel(/email/i)).toBeVisible();
  await expect(page.getByLabel(/password/i)).toBeVisible();

  await assertNoHorizontalOverflow(page);
  await attachScreenshot(page, "login-mobile");
});

for (const viewport of [
  { name: "workspace-desktop", size: { width: 1440, height: 1400 } },
  { name: "workspace-mobile", size: { width: 430, height: 1400 } },
]) {
  test(`lead workspace layout is stable on ${viewport.name}`, async ({ page }) => {
    await page.setViewportSize(viewport.size);
    await login(page);
    await page.goto("/app/leads");

    await expect(page.getByRole("heading", { name: /qualification workspace/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: /lead queue/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: /lead map/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: /selected lead/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /open lead detail/i })).toBeVisible();

    await assertNoHorizontalOverflow(page);
    await attachScreenshot(page, viewport.name);
  });
}

for (const routeCase of [
  {
    name: "overview-desktop",
    path: "/app",
    heading: /lead desk snapshot/i,
  },
  {
    name: "searches-desktop",
    path: "/app/searches",
    heading: /launch a scoped lead discovery run/i,
  },
  {
    name: "settings-desktop",
    path: "/app/settings",
    heading: /operational configuration/i,
  },
]) {
  test(`${routeCase.name} remains stable`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1400 });
    await login(page);
    await page.goto(routeCase.path);

    await expect(page.getByRole("heading", { name: routeCase.heading })).toBeVisible();
    await assertNoHorizontalOverflow(page);
    await attachScreenshot(page, routeCase.name);
  });
}
