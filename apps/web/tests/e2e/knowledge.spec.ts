import { test, expect } from "./fixtures";
import { authStatePath } from "./helpers/auth";
import { expectNoHorizontalOverflow, gotoPath } from "./helpers/page";
import { MOCK_IDS } from "./support/mock-api";

test.use({ storageState: authStatePath });

const KNOWLEDGE_PATH = "/app/knowledge";

async function createCollection(page: import("@playwright/test").Page, name: string) {
  await page.getByRole("button", { name: /new collection/i }).first().click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel(/^name$/i).fill(name);
  await dialog.getByRole("button", { name: /^create$/i }).click();
  await expect(dialog).toBeHidden();
}

/** Toasts pause while hovered and, on small screens, cover the controls beneath them. */
async function waitForToastsToClear(page: import("@playwright/test").Page) {
  await page.mouse.move(0, 0);
  await expect(page.locator("[data-sonner-toast]")).toHaveCount(0, { timeout: 15_000 });
}

test("empty state guides the user to create a collection first", async ({ page }) => {
  await gotoPath(page, KNOWLEDGE_PATH);
  await expect(page.getByRole("heading", { name: /sales knowledge/i, level: 1 })).toBeVisible();
  await expect(page.getByText(/create a collection first/i)).toBeVisible();
  await expect(page.getByRole("button", { name: /add document/i })).toBeDisabled();
  await expectNoHorizontalOverflow(page);
});

test("upload, search, replace and remove a document end to end", async ({ page }) => {
  await gotoPath(page, KNOWLEDGE_PATH);
  await createCollection(page, "Case studies");

  // Upload a markdown file: content and a derived title are filled in for review.
  await page.getByRole("button", { name: /add document/i }).first().click();
  const dialog = page.getByRole("dialog");
  await dialog.locator('input[type="file"]').setInputFiles({
    name: "dental-booking-case.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Dental booking\n\nWe added online booking for a dental clinic and doubled appointments."),
  });
  await expect(dialog.getByLabel(/^title$/i)).toHaveValue("dental booking case");
  await dialog.getByRole("button", { name: /add and index/i }).click();

  const row = page
    .getByRole("region", { name: /^documents$/i })
    .getByRole("listitem")
    .filter({ hasText: "dental booking case" });
  await expect(row).toBeVisible();
  await expect(row.getByText(/^ready$/i)).toBeVisible();
  // The mock index is keyword-only, and the UI says so instead of claiming semantic search.
  await expect(page.getByText(/keyword search only/i).first()).toBeVisible();

  await waitForToastsToClear(page);

  // The copilot's view of the knowledge: search finds it and marks results as keyword-only.
  await page.getByRole("search").getByRole("textbox").fill("online booking");
  await page.getByRole("search").getByRole("button", { name: /^search$/i }).click();
  await expect(page.getByText(/keyword matching only/i)).toBeVisible();
  await expect(page.getByRole("list").getByText("dental booking case").last()).toBeVisible();

  // Replacing with identical content reports that nothing changed rather than success.
  await row.getByRole("button", { name: /replace content/i }).click();
  await page
    .getByRole("dialog")
    .getByLabel(/^content$/i)
    .fill("# Dental booking\n\nWe added online booking for a dental clinic and doubled appointments.");
  await page.getByRole("dialog").getByRole("button", { name: /replace and re-index/i }).click();
  await expect(page.getByText(/nothing changed/i)).toBeVisible();

  await waitForToastsToClear(page);

  // Removing asks for confirmation, is worded as "removed from answers", and is server-confirmed.
  await row.getByRole("button", { name: /remove .* from answers/i }).click();
  await expect(page.getByRole("alertdialog")).toContainText(/no longer be used to answer questions/i);
  await page.getByRole("alertdialog").getByRole("button", { name: /remove from answers/i }).click();
  await expect(row).toHaveCount(0);
  await waitForToastsToClear(page);

  await page.getByRole("search").getByRole("textbox").fill("online booking");
  await page.getByRole("search").getByRole("button", { name: /^search$/i }).click();
  await expect(page.getByText(/nothing relevant found/i)).toBeVisible();
});

test("unsupported and empty files are refused with a clear reason", async ({ page }) => {
  await gotoPath(page, KNOWLEDGE_PATH);
  await createCollection(page, "Pricing");
  await page.getByRole("button", { name: /add document/i }).first().click();
  const dialog = page.getByRole("dialog");
  const input = dialog.locator('input[type="file"]');

  await input.setInputFiles({ name: "deck.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4") });
  await expect(dialog.getByRole("alert")).toContainText(/isn't supported/i);
  await expect(dialog.getByRole("button", { name: /add and index/i })).toBeDisabled();

  await input.setInputFiles({ name: "blank.txt", mimeType: "text/plain", buffer: Buffer.from("  \n ") });
  await expect(dialog.getByRole("alert")).toContainText(/no text/i);
});

test.describe("as a member", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("restricted visibility is not offered", async ({ page }) => {
    await gotoPath(page, "/login");
    await page.getByLabel(/email/i).fill(MOCK_IDS.memberEmail);
    await page.getByLabel(/password/i).fill(MOCK_IDS.memberPassword);
    await page.getByRole("button", { name: /open workspace/i }).click();
    await expect(page).toHaveURL(/\/app$/);

    await gotoPath(page, KNOWLEDGE_PATH);
    await createCollection(page, "Notes");
    await page.getByRole("button", { name: /add document/i }).first().click();
    await page.getByRole("dialog").getByRole("combobox", { name: /who can use it/i }).click();
    await expect(page.getByRole("option", { name: /whole workspace/i })).toBeVisible();
    await expect(page.getByRole("option", { name: /managers and admins/i })).toHaveCount(0);
  });
});
