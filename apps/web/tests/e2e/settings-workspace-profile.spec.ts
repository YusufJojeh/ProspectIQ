import { test, expect } from "./fixtures";
import { authStatePath } from "./helpers/auth";
import { gotoPath } from "./helpers/page";
import { routes } from "./helpers/routes";

test.use({ storageState: authStatePath });

test("workspace profession selector persists the chosen profession", async ({
  page,
}) => {
  await gotoPath(page, routes.settings);

  await expect(page.getByText(/workspace profile/i).first()).toBeVisible();

  const professionField = page.locator(
    '[aria-label="Profession / industry"]',
  );
  await professionField.click();
  await page.getByRole("option", { name: /real estate/i }).click();

  const [request] = await Promise.all([
    page.waitForRequest(
      (req) =>
        req.url().includes("/api/v1/workspace-settings") &&
        req.method() === "PATCH",
    ),
    page.getByRole("button", { name: /save workspace profile/i }).click(),
  ]);

  const body = request.postDataJSON() as {
    settings?: { profession?: string };
  };
  expect(body.settings?.profession).toBe("real_estate");

  await page.reload();
  await expect(
    page.locator('[aria-label="Profession / industry"]'),
  ).toContainText(/real estate/i);
});

test("scoring configuration form includes the web search confidence weight", async ({
  page,
}) => {
  await gotoPath(page, routes.settings);

  await page.getByRole("tab", { name: /^Scoring config/i }).click();

  await expect(
    page.getByRole("spinbutton", { name: "web_search_confidence" }),
  ).toBeVisible();
});
