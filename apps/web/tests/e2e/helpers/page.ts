import { expect, type Locator, type Page } from "@playwright/test";

export function isDesktopWideProject(projectName: string) {
  return projectName === "desktop-wide";
}

export function usesCompactAppNav(projectName: string) {
  return projectName === "tablet" || projectName === "mobile";
}

export function isMobileProject(projectName: string) {
  return projectName === "mobile";
}

export function isTabletProject(projectName: string) {
  return projectName === "tablet";
}

export async function waitForPageReady(page: Page) {
  await page.waitForLoadState("domcontentloaded");
  await page.evaluate(async () => {
    if ("fonts" in document) {
      await document.fonts.ready;
    }
  });
}

export async function gotoPath(page: Page, path: string) {
  await page.goto(path);
  await waitForPageReady(page);
}

export async function delayApiResponseOnce(page: Page, urlPattern: string | RegExp, delayMs = 1200) {
  const handler = async (route: Parameters<Page["route"]>[1] extends (route: infer R) => unknown ? R : never) => {
    await new Promise((resolve) => setTimeout(resolve, delayMs));
    await route.continue();
    await page.unroute(urlPattern, handler);
  };
  await page.route(urlPattern, handler);
}

export async function expectNoHorizontalOverflow(page: Page) {
  await page.waitForTimeout(250);
  const { overflow, offenders } = await page.evaluate(() => {
    const offenders = [...document.body.querySelectorAll("*")]
      .filter((element) => {
        if (element.closest(".leaflet-container")) {
          return false;
        }

        const style = window.getComputedStyle(element);
        if (style.position === "absolute" || style.position === "fixed") {
          return false;
        }

        const scrollParent = element.closest<HTMLElement>('[data-slot="table-container"], .overflow-x-auto, .overflow-x-scroll');
        if (scrollParent) {
          return false;
        }

        const rect = element.getBoundingClientRect();
        return rect.width > 0 && rect.right - window.innerWidth > 1;
      })
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          overflow: rect.right - window.innerWidth,
          tag: element.tagName.toLowerCase(),
          className: element.className,
          text: (element.textContent ?? "").trim().slice(0, 80),
        };
      })
      .sort((a, b) => b.overflow - a.overflow);

    return {
      overflow: Math.max(0, ...offenders.map((entry) => entry.overflow)),
      offenders: offenders.slice(0, 5),
    };
  });
  if (overflow > 1) {
    throw new Error(`Horizontal overflow detected: ${overflow}px :: ${JSON.stringify(offenders)}`);
  }
}

export async function expectStableScreenshot(locator: Locator, name: string) {
  await expect(locator).toHaveScreenshot(name);
}
