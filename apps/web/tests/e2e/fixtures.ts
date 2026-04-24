import { expect, test as base } from "@playwright/test";
import { installMockApi } from "./support/mock-api";

export const test = base.extend({
  page: async ({ page }, use) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await installMockApi(page);
    await use(page);
  },
});

export { expect };
