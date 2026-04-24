import { describe, expect, it } from "vitest";
import { bandTone, searchJobTone, statusTone } from "@/lib/presenters";

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
});
