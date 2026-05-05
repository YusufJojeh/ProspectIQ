import { expect, test as base } from "@playwright/test";
import { installMockApi } from "./support/mock-api";

export const test = base.extend({
  page: async ({ page }, use) => {
    const consoleErrors: string[] = [];
    const responseErrors: string[] = [];

    page.on("console", (message) => {
      if (message.type() === "error") {
        const text = message.text();
        if (
          !/Failed to load resource: the server responded with a status of 404/i.test(text) &&
          !/Failed to load resource: the server responded with a status of 403 \(Forbidden\)/i.test(text) &&
          !/`DialogContent` requires a `DialogTitle`/i.test(text)
        ) {
          consoleErrors.push(text);
        }
      }
    });

    page.on("response", (response) => {
      if (response.status() >= 500) {
        responseErrors.push(`${response.status()} ${response.request().method()} ${response.url()}`);
      }
    });

    await page.emulateMedia({ reducedMotion: "reduce" });
    await installMockApi(page);
    await use(page);

    expect.soft(consoleErrors, "Unexpected browser console errors").toEqual([]);
    expect.soft(responseErrors, "Unexpected 5xx responses").toEqual([]);
  },
});

export { expect };
