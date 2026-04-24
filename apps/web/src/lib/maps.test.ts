import { describe, expect, it } from "vitest";
import { hasCoordinates, toLatLngTuple } from "@/lib/maps";

describe("maps helpers", () => {
  it("accepts valid coordinates and returns a tuple", () => {
    const point = { lat: 41.015, lng: 29.042 };

    expect(hasCoordinates(point)).toBe(true);
    expect(toLatLngTuple(point)).toEqual([41.015, 29.042]);
  });

  it("rejects null or non-finite coordinates", () => {
    expect(hasCoordinates({ lat: null, lng: 29.042 })).toBe(false);
    expect(hasCoordinates({ lat: Number.NaN, lng: 29.042 })).toBe(false);
    expect(hasCoordinates({ lat: 41.015, lng: Number.POSITIVE_INFINITY })).toBe(false);
  });

  it("rejects coordinates outside the supported map range", () => {
    expect(hasCoordinates({ lat: 91, lng: 29.042 })).toBe(false);
    expect(hasCoordinates({ lat: 41.015, lng: -181 })).toBe(false);
  });
});
