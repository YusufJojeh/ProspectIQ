import { describe, expect, it } from "vitest";

import type { BrandFields } from "@/types/proposals";

import { brandFormSchema, sampleDocument, toBrandFormValues, toBrandRequest } from "./brand-form";

const brand: BrandFields = {
  name: "Bright Smile Dental",
  tagline: "Family dentistry",
  mark: "BS",
  mark_shape: "circle",
  font_style: "serif",
  logo_data_url: null,
  number_prefix: "bsd-q",
  signer_label: "For Bright Smile",
  client_signer_label: "Client",
  footer_contact: "hello@brightsmile.test",
  paper: "#ffffff",
  ink: "#111111",
  muted: "#666666",
  line: "#DDDDDD",
  accent: "#0E7490",
  accent_secondary: "#F59E0B",
  background: "#F8FAFC",
  radius_px: 6,
  default_currency: "eur",
  validity_days: 14,
  default_outcome: "A calmer front desk.",
  default_commercial_notes: "",
  default_validity_notes: "Valid for 14 days.",
  default_milestones: [{ title: " Setup ", description: "" }],
};

describe("brand form", () => {
  it("normalises a tenant's brand into a request", () => {
    const request = toBrandRequest(brandFormSchema.parse(toBrandFormValues(brand)));
    expect(request.number_prefix).toBe("BSD-Q");
    expect(request.default_currency).toBe("EUR");
    expect(request.paper).toBe("#FFFFFF");
    expect(request.default_milestones).toEqual([{ title: "Setup", description: "" }]);
  });

  it("rejects bad colours, prefixes and currencies", () => {
    const result = brandFormSchema.safeParse({
      ...toBrandFormValues(brand),
      accent: "red",
      number_prefix: "BAD PREFIX",
      default_currency: "EURO",
    });
    expect(result.success).toBe(false);
    const messages = result.success ? [] : result.error.issues.map((issue) => issue.message);
    expect(messages).toEqual(expect.arrayContaining(["invalidColor", "invalidPrefix", "invalidCurrency"]));
  });

  it("previews the brand with its own numbering, currency and validity", () => {
    const doc = sampleDocument(toBrandFormValues(brand), "en", "2026-10-11", {
      clientCompany: "Sample",
      title: "Project",
    });
    expect(doc.number).toBe("BSD-Q-2026-001");
    expect(doc.currency).toBe("EUR");
    expect(doc.valid_until).toBe("2026-10-25");
    expect(doc.milestones).toHaveLength(1);
  });
});
