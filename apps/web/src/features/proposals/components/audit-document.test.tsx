import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { BrandFields } from "@/types/proposals";

import { AuditDocument, type AuditDocumentData } from "./audit-document";

const brand: BrandFields = {
  name: "Bright Smile Dental",
  tagline: "",
  mark: "BS",
  mark_shape: "circle",
  font_style: "sans",
  logo_data_url: null,
  number_prefix: "BSD-Q",
  signer_label: "",
  client_signer_label: "",
  footer_contact: "hello@brightsmile.test",
  paper: "#FFFFFF",
  ink: "#111111",
  muted: "#666666",
  line: "#DDDDDD",
  accent: "#0E7490",
  accent_secondary: "#F59E0B",
  background: "#F8FAFC",
  radius_px: 6,
  default_currency: "EUR",
  validity_days: 14,
  default_outcome: "",
  default_commercial_notes: "",
  default_validity_notes: "",
  default_milestones: [],
};

const data: AuditDocumentData = {
  brand,
  language: "en",
  companyName: "Acme Dental",
  category: "Dentist",
  city: "Istanbul",
  websiteUrl: null,
  generatedOn: "2026-10-11",
  findings: [
    { key: "website", status: "missing", values: { peer_pct: 75 } },
    { key: "reviews", status: "good", values: { count: 140 } },
  ],
  benchmark: { peer_count: 4, median_rating: 4.8, median_reviews: 90, website_pct: 75 },
  evidence: [],
  note: "",
  nextStep: "",
};

describe("AuditDocument", () => {
  afterEach(cleanup);

  it("leads with the opportunities and compares with nearby businesses", () => {
    render(<AuditDocument data={data} />);
    expect(screen.getByText("1 opportunity to win more customers")).toBeInTheDocument();
    expect(screen.getByText("No website found")).toBeInTheDocument();
    expect(screen.getByText("Compared with 4 similar businesses nearby")).toBeInTheDocument();
    expect(screen.getByText("hello@brightsmile.test", { selector: "b" })).toBeInTheDocument();
  });

  it("renders right-to-left in Arabic", () => {
    render(<AuditDocument data={{ ...data, language: "ar" }} />);
    const article = screen.getByRole("article");
    expect(article).toHaveAttribute("dir", "rtl");
    expect(screen.getByText("لم نجد موقعًا إلكترونيًا")).toBeInTheDocument();
  });
});
