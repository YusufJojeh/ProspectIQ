import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:4173";
const apiBaseURL = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";
const artifactRoot = process.env.PLAYWRIGHT_ARTIFACT_ROOT ?? "test-artifacts/playwright";
const authStatePath = path.resolve(process.cwd(), "tests/e2e/.auth/admin.json");

export default defineConfig({
  testDir: "./tests/e2e",
  testIgnore: ["**/support/**", "**/helpers/**"],
  timeout: 45_000,
  expect: {
    timeout: 8_000,
    toHaveScreenshot: {
      animations: "disabled",
      caret: "hide",
      scale: "css",
      maxDiffPixelRatio: 0.01,
    },
  },
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  outputDir: `${artifactRoot}/test-results`,
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: `${artifactRoot}/report` }],
  ],
  use: {
    baseURL,
    headless: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "setup",
      testMatch: /setup[\\/].*\.setup\.ts/,
      use: {
        viewport: { width: 1280, height: 900 },
        channel: process.platform === "win32" ? "chrome" : undefined,
      },
    },
    {
      name: "desktop-wide",
      dependencies: ["setup"],
      testIgnore: /setup[\\/].*\.setup\.ts/,
      use: {
        viewport: { width: 1536, height: 960 },
        storageState: undefined,
        channel: process.platform === "win32" ? "chrome" : undefined,
      },
    },
    {
      name: "laptop",
      dependencies: ["setup"],
      testIgnore: /setup[\\/].*\.setup\.ts/,
      use: {
        viewport: { width: 1366, height: 900 },
        storageState: undefined,
        channel: process.platform === "win32" ? "chrome" : undefined,
      },
    },
    {
      name: "tablet",
      dependencies: ["setup"],
      testIgnore: /setup[\\/].*\.setup\.ts/,
      use: {
        ...devices["iPad (gen 7)"],
        storageState: undefined,
      },
    },
    {
      name: "mobile",
      dependencies: ["setup"],
      testIgnore: /setup[\\/].*\.setup\.ts/,
      use: {
        ...devices["iPhone 13"],
        storageState: undefined,
      },
    },
  ],
  webServer: {
    command: "npm run dev:e2e",
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    env: {
      VITE_API_BASE_URL: apiBaseURL,
    },
  },
  metadata: {
    authStatePath,
  },
});
