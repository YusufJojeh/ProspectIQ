import type { Page } from "@playwright/test";

import { test, expect } from "./fixtures";
import { authStatePath } from "./helpers/auth";
import { gotoPath } from "./helpers/page";
import { routes } from "./helpers/routes";
import { installAgentMock } from "./support/agent-mock";

test.use({ storageState: authStatePath });

function json(route: import("@playwright/test").Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

async function ask(page: Page) {
  await page.getByLabel(/ask the copilot/i).fill("Why is this a good fit?");
  await page.getByRole("button", { name: /^ask$/i }).click();
}

test.describe("Sales Copilot approval flow", () => {
  test("a proposed write stays pending until the server confirms approval", async ({ page }) => {
    const mock = await installAgentMock(page, { approveDelayMs: 400 });
    await gotoPath(page, routes.leadDetail);
    await ask(page);

    const approvals = page.getByRole("region", { name: /waiting for your approval/i });
    await expect(approvals).toBeVisible();
    await expect(approvals.getByText("Booking gap confirmed on the website.")).toBeVisible();
    await expect(approvals.getByText(/^pending$/i)).toBeVisible();
    // A proposal is not a mutation: no "Applied" anywhere and no final answer yet.
    await expect(page.getByText(/^applied$/i)).toHaveCount(0);
    await expect(page.getByText(/strong fit/i)).toHaveCount(0);

    await approvals.getByRole("button", { name: /^approve$/i }).click();

    // While the request is in flight the action must not be shown as applied.
    await expect(approvals.getByRole("button", { name: /approving/i })).toBeDisabled();
    await expect(page.getByText(/^applied$/i)).toHaveCount(0);

    await expect(page.getByText(/strong fit/i)).toBeVisible();
    await expect(page.getByText(/^applied$/i).first()).toBeVisible();
    expect(mock.approveCalls).toBe(1);
  });

  test("declining a change records the decision and never shows it as applied", async ({ page }) => {
    const mock = await installAgentMock(page);
    await gotoPath(page, routes.leadDetail);
    await ask(page);

    const approvals = page.getByRole("region", { name: /waiting for your approval/i });
    await approvals.getByRole("button", { name: /^decline$/i }).click();
    await approvals.getByRole("button", { name: /decline change/i }).click();

    await expect(page.getByText(/^declined$/i).first()).toBeVisible();
    await expect(page.getByText(/^applied$/i)).toHaveCount(0);
    expect(mock.rejectCalls).toBe(1);
    expect(mock.approveCalls).toBe(0);
  });

  test("the final answer separates lead evidence from internal knowledge and shows no raw JSON", async ({ page }) => {
    await installAgentMock(page);
    await gotoPath(page, routes.leadDetail);
    await ask(page);
    await page
      .getByRole("region", { name: /waiting for your approval/i })
      .getByRole("button", { name: /^approve$/i })
      .click();

    await expect(page.getByText(/strong fit/i)).toBeVisible();
    await expect(page.getByRole("heading", { name: /from your sales knowledge/i })).toBeVisible();
    const body = await page.locator("main").innerText();
    expect(body).not.toMatch(/"tool_name"|"action_id"|\{"/);
  });

  test("a server error is shown as a failure, not as a completed answer", async ({ page }) => {
    await page.route("**/api/v1/agent/runs", async (route) => {
      if (route.request().method() === "POST") return json(route, { detail: "Forbidden" }, 403);
      return route.fallback();
    });
    await gotoPath(page, routes.leadDetail);
    await ask(page);

    await expect(page.getByRole("alert").first()).toBeVisible();
    await expect(page.getByText(/^applied$/i)).toHaveCount(0);
    await expect(page.getByText(/strong fit/i)).toHaveCount(0);
  });
});
