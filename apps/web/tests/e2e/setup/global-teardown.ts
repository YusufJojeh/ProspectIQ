import { readFile, rm } from "node:fs/promises";
import { spawn } from "node:child_process";
import path from "node:path";

const pidPath = path.resolve(process.cwd(), "test-artifacts/playwright/web-server.pid");

function stopProcess(pid: number): Promise<void> {
  return new Promise((resolve) => {
    if (process.platform === "win32") {
      const killer = spawn("taskkill", ["/pid", String(pid), "/t", "/f"], { stdio: "ignore" });
      killer.on("exit", () => resolve());
      killer.on("error", () => resolve());
      return;
    }

    try {
      process.kill(-pid, "SIGTERM");
    } catch {
      try {
        process.kill(pid, "SIGTERM");
      } catch {
        return resolve();
      }
    }
    resolve();
  });
}

async function globalTeardown(): Promise<void> {
  if (process.env.PLAYWRIGHT_SKIP_WEBSERVER === "1") {
    return;
  }

  let pid: number | undefined;
  try {
    const rawPid = await readFile(pidPath, "utf8");
    pid = Number(rawPid.trim());
  } catch {
    return;
  }

  if (Number.isFinite(pid) && pid > 0) {
    await stopProcess(pid);
  }
  await rm(pidPath, { force: true });
}

export default globalTeardown;
