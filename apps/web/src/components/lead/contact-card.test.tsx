import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LeadContactCard } from "@/components/lead/contact-card";

afterEach(() => cleanup());

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        "leadContact.notAvailable": "Not available",
        "leadContact.openLinkedin": "Open company page",
      };
      return map[key] ?? key;
    },
    i18n: { changeLanguage: vi.fn() },
  }),
}));

import type { LeadResponse } from "@/types/api";

const baseLead: LeadResponse = {
  public_id: "lead_1",
  company_name: "North Dental",
  category: "Dentist",
  address: null,
  city: "Istanbul",
  phone: null,
  website_url: "https://north.example",
  website_domain: "north.example",
  review_count: 24,
  rating: 4.7,
  lat: null,
  lng: null,
  data_completeness: 0.9,
  data_confidence: 0.88,
  has_website: true,
  email: "hello@north.example",
  email_confidence: 0.8,
  linkedin_url: "https://linkedin.com/company/north",
  industry: "Dentist",
  employee_count: 12,
  ai_opener: "North Dental has strong local trust.",
  logo_url: "https://logo.clearbit.com/north.example",
  status: "new",
  assigned_to_user_public_id: null,
  latest_score: 82,
  latest_fit_score: null,
  latest_need_score: null,
  latest_urgency_score: null,
  latest_reachability_score: null,
  latest_final_priority_score: null,
  latest_band: "high",
  latest_qualified: true,
  latest_outreach_status: null,
  top_signal_type: null,
  top_signal_strength: null,
  top_signal_evidence: null,
  signals_count: 0,
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z",
};

describe("LeadContactCard", () => {
  it("renders populated contact fields", () => {
    render(<LeadContactCard lead={baseLead} />);
    expect(screen.getByText("Dentist")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "hello@north.example" })).toHaveAttribute(
      "href",
      "mailto:hello@north.example",
    );
    expect(screen.getByRole("link", { name: /open company page/i })).toHaveAttribute(
      "href",
      "https://linkedin.com/company/north",
    );
    expect(screen.getByText("North Dental has strong local trust.")).toBeInTheDocument();
  });

  it("shows empty states when fields are missing", () => {
    const lead: LeadResponse = {
      ...baseLead,
      email: null,
      email_confidence: null,
      linkedin_url: null,
      industry: null,
      employee_count: null,
      ai_opener: null,
    };
    render(<LeadContactCard lead={lead} />);
    expect(screen.getAllByText("Not available").length).toBeGreaterThanOrEqual(4);
    expect(screen.queryByRole("link", { name: /open company page/i })).toBeNull();
  });
});
