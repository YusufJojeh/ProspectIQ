import { test, expect } from "./fixtures";
import { authStatePath } from "./helpers/auth";
import { gotoPath } from "./helpers/page";
import { routes } from "./helpers/routes";
import { MOCK_IDS } from "./support/mock-api";
import { installAgentMock } from "./support/agent-mock";

test.use({ storageState: authStatePath });

test.describe("Standalone Sales Copilot page", () => {
  test("opens in workspace mode and runs without a lead", async ({ page }) => {
    await installAgentMock(page);
    const runPayloads: Array<Record<string, unknown>> = [];
    page.on("request", (request) => {
      if (request.method() === "POST" && request.url().endsWith("/api/v1/agent/runs")) {
        runPayloads.push(request.postDataJSON() as Record<string, unknown>);
      }
    });

    await gotoPath(page, routes.copilot);
    await expect(page.getByRole("heading", { name: /sales copilot/i }).first()).toBeVisible();
    await expect(page.getByText(/no lead selected/i)).toBeVisible();
    await expect(page.getByText(/what services do we offer/i)).toBeVisible();

    await page.getByLabel(/ask the copilot/i).fill("What services do we offer?");
    await page.getByRole("button", { name: /^ask$/i }).click();
    await expect(page.getByRole("region", { name: /waiting for your approval/i })).toBeVisible();

    expect(runPayloads).toHaveLength(1);
    expect(runPayloads[0]?.lead_id ?? null).toBeNull();
  });

  test("binds the copilot to a lead picked from the sidebar", async ({ page }) => {
    await installAgentMock(page);
    await gotoPath(page, routes.copilot);

    await page
      .getByRole("list", { name: /matching leads/i })
      .getByRole("button", { name: /acme dental/i })
      .click();

    await expect(page).toHaveURL(new RegExp(`leadId=${MOCK_IDS.primaryLeadId}`));
    await expect(page.getByRole("link", { name: /open lead/i })).toHaveAttribute(
      "href",
      `/app/leads/${MOCK_IDS.primaryLeadId}`,
    );
    await expect(page.getByText(/no lead selected/i)).toHaveCount(0);

    await page.getByRole("button", { name: /^clear$/i }).click();
    await expect(page).not.toHaveURL(/leadId=/);
    await expect(page.getByText(/no lead selected/i)).toBeVisible();
  });
});
