import { spawn, type ChildProcess } from "node:child_process";
import { mkdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import type { FullConfig } from "@playwright/test";

const pidPath = path.resolve(
  process.cwd(),
  "test-artifacts/playwright/web-server.pid",
);

async function isReachable(url: string): Promise<boolean> {
  try {
    const response = await fetch(url, { method: "HEAD" });
    return response.ok || response.status < 500;
  } catch {
    return false;
  }
}

async function waitForServer(url: string, child: ChildProcess): Promise<void> {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) {
      throw new Error(
        `Playwright web server exited early with code ${child.exitCode}.`,
      );
    }
    if (await isReachable(url)) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`Timed out waiting for Playwright web server at ${url}.`);
}

async function globalSetup(config: FullConfig): Promise<void> {
  if (process.env.PLAYWRIGHT_SKIP_WEBSERVER === "1") {
    return;
  }

  const baseURL = String(
    config.projects[0]?.use.baseURL ?? "http://127.0.0.1:4173",
  );
  if (await isReachable(baseURL)) {
    await rm(pidPath, { force: true });
    return;
  }

  await mkdir(path.dirname(pidPath), { recursive: true });
  const child = spawn(
    process.execPath,
    [
      "./node_modules/vite/bin/vite.js",
      "preview",
      "--host",
      "127.0.0.1",
      "--port",
      "4173",
      "--strictPort",
    ],
    {
      cwd: process.cwd(),
      detached: false,
      env: {
        ...process.env,
        VITE_API_BASE_URL:
          process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000",
      },
      stdio: "ignore",
    },
  );
  if (!child.pid) {
    throw new Error("Failed to start Playwright web server process.");
  }
  child.unref();
  await writeFile(pidPath, String(child.pid), "utf8");
  await waitForServer(baseURL, child);
}

export default globalSetup;
