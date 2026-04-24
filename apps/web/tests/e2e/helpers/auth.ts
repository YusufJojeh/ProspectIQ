import fs from "node:fs/promises";
import path from "node:path";
import { expect, type Page } from "@playwright/test";
import { MOCK_IDS } from "../support/mock-api";

export const authStatePath = path.resolve(process.cwd(), "tests/e2e/.auth/admin.json");

export async function ensureAuthStateDir() {
  await fs.mkdir(path.dirname(authStatePath), { recursive: true });
}

export async function loginThroughUi(page: Page) {
  await page.goto("/login");
  await expect(page.getByText(/sign in to your leadscope workspace/i)).toBeVisible();
  await page.getByLabel(/email/i).fill(MOCK_IDS.adminEmail);
  await page.getByLabel(/password/i).fill(MOCK_IDS.adminPassword);
  await page.getByRole("button", { name: /open workspace/i }).click();
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByRole("link", { name: "Dashboard", exact: true })).toBeVisible();
}
