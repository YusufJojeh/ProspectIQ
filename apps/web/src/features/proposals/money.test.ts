import { describe, expect, it } from "vitest";

import { formatMinor, formatMoney, minorToInput, parseMinor } from "./money";

describe("proposal money", () => {
  it("formats minor units with grouping and two decimals", () => {
    expect(formatMinor(750_000)).toBe("7,500.00");
    expect(formatMinor(5)).toBe("0.05");
    expect(formatMinor(123_456_789)).toBe("1,234,567.89");
    expect(formatMinor(null)).toBe("—");
    expect(formatMoney("USD", 150_000)).toBe("USD 1,500.00");
    expect(formatMoney("USD", null)).toBe("—");
  });

  it("parses what people type", () => {
    expect(parseMinor("7,500")).toBe(750_000);
    expect(parseMinor(" 12 000.5 ")).toBe(1_200_050);
    expect(parseMinor("0.05")).toBe(5);
    expect(parseMinor("")).toBeNull();
    expect(parseMinor("-5")).toBeUndefined();
    expect(parseMinor("1.234")).toBeUndefined();
    expect(parseMinor("abc")).toBeUndefined();
  });

  it("round-trips through the input format", () => {
    for (const value of [0, 5, 150_000, 1_200_050]) {
      expect(parseMinor(minorToInput(value))).toBe(value);
    }
    expect(minorToInput(null)).toBe("");
  });
});
