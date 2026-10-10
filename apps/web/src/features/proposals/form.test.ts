import { describe, expect, it } from "vitest";

import type { Proposal } from "@/types/proposals";

import { proposalFormSchema, toFormValues, toUpdateRequest } from "./form";

const proposal: Proposal = {
  public_id: "prop_1",
  number: "YJ-Q-2026-001",
  status: "draft",
  lead_id: "lead_1",
  lead_company_name: "Acme Dental",
  brand: {
    public_id: "pbrand_1",
    is_default: true,
    archived: false,
    name: "Yusuf Jojeh",
    tagline: "Backend & Business Systems Engineer",
    mark: "YJ",
    mark_shape: "square",
    font_style: "sans",
    logo_data_url: null,
    number_prefix: "YJ-Q",
    signer_label: "Yusuf Mohammad Jojeh",
    client_signer_label: "Client · Name / role / date",
    footer_contact: "linkedin.com/in/yusuf-jojeh",
    paper: "#F5F2EA",
    ink: "#151719",
    muted: "#6D7379",
    line: "#D8D4CB",
    accent: "#E45D34",
    accent_secondary: "#9CA6AF",
    background: "#0A0C0F",
    radius_px: 8,
    default_currency: "USD",
    validity_days: 30,
    default_outcome: "",
    default_commercial_notes: "",
    default_validity_notes: "",
    default_milestones: [],
  },
  language: "en",
  title: "Booking",
  client_company: "Acme Dental",
  client_contact_name: null,
  client_email: null,
  client_location: "Dubai",
  currency: "USD",
  issue_date: "2026-10-10",
  valid_until: "2026-11-09",
  outcome: "Outcome",
  milestones: [
    { title: "Discovery", description: "", amount_minor: 150_000, share_pct: 100 },
    { title: "Build", description: "", amount_minor: null, share_pct: null },
  ],
  commercial_notes: "Notes",
  validity_notes: "30 days",
  sender_contact: "linkedin.com/in/yusuf-jojeh",
  pricing_basis: null,
  source_agent_run_id: null,
  totals: { total_minor: 150_000, deposit_minor: 150_000, remaining_minor: 0 },
  readiness: { ready: false, issues: ["milestone_missing_amount"] },
  sent_at: null,
  decided_at: null,
  created_at: "2026-10-10T00:00:00",
  updated_at: "2026-10-10T00:00:00",
};

describe("proposal form", () => {
  it("round-trips a proposal through the form without changing it", () => {
    const values = toFormValues(proposal);
    expect(values.milestones.map((line) => line.amount)).toEqual(["1500", ""]);
    const request = toUpdateRequest(values);
    expect(request.milestones?.map((line) => line.amount_minor)).toEqual([150_000, null]);
    expect(request.client_email).toBeNull();
    expect(proposalFormSchema.safeParse(values).success).toBe(true);
  });

  it("rejects malformed amounts, emails and dates", () => {
    const values = toFormValues(proposal);
    const badAmount = { ...values, milestones: [{ title: "x", description: "", amount: "12.345" }] };
    expect(proposalFormSchema.safeParse(badAmount).success).toBe(false);
    expect(proposalFormSchema.safeParse({ ...values, client_email: "nope" }).success).toBe(false);
    expect(
      proposalFormSchema.safeParse({ ...values, valid_until: values.issue_date }).success,
    ).toBe(false);
  });
});
