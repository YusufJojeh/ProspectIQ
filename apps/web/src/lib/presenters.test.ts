import { describe, expect, it } from "vitest";
import {
  bandTone,
  formatRelativeTime,
  searchJobTone,
  statusTone,
} from "@/lib/presenters";

describe("presenter tone helpers", () => {
  it("maps score bands to the expected badge tones", () => {
    expect(bandTone("high")).toBe("success");
    expect(bandTone("medium")).toBe("accent");
    expect(bandTone("low")).toBe("accent");
    expect(bandTone(null)).toBe("neutral");
  });

  it("maps lead statuses to semantically consistent badge tones", () => {
    expect(statusTone("qualified")).toBe("success");
    expect(statusTone("contacted")).toBe("accent");
    expect(statusTone("lost")).toBe("danger");
    expect(statusTone("new")).toBe("neutral");
  });

  it("maps search job statuses to consistent badge tones", () => {
    expect(searchJobTone("completed")).toBe("success");
    expect(searchJobTone("partially_completed")).toBe("warning");
    expect(searchJobTone("failed")).toBe("danger");
    expect(searchJobTone("running")).toBe("accent");
    expect(searchJobTone("queued")).toBe("accent");
  });

  it("formats relative time from the supplied current time", () => {
    expect(
      formatRelativeTime(
        "2026-05-30T20:59:30.000Z",
        "en",
        new Date("2026-05-30T21:00:00.000Z"),
      ),
    ).toBe("30 seconds ago");
    expect(
      formatRelativeTime(
        "2026-05-30T20:58:00.000Z",
        "en",
        new Date("2026-05-30T21:00:00.000Z"),
      ),
    ).toBe("2 minutes ago");
  });
});
