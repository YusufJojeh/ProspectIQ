import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { LeadAiAnalysisPanel } from "@/components/lead/ai-analysis-panel";

// i18n is not initialised in unit tests; stub useTranslation so that
// t("key") returns the final English string rather than the bare key.
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        "leadDetail.askAssistant": "Ask assistant about this lead",
        "leadDetail.recommendedServices": "Recommended services",
      };
      return map[key] ?? key;
    },
    i18n: { changeLanguage: vi.fn() },
  }),
}));
import type { LeadAnalysisSnapshotResponse } from "@/types/api";

const snapshot: LeadAnalysisSnapshotResponse = {
  public_id: "analysis_123",
  lead_id: "lead_123",
  ai_provider: "openai",
  model_name: "gpt-4.1-mini",
  created_at: "2026-04-29T10:15:00Z",
  analysis: {
    summary:
      "## Strong fit\n\nThis lead has **high local trust** and clear digital demand.",
    opportunities: [
      "Prioritize **local SEO** because discoverability gaps are still visible.",
    ],
    weaknesses: [
      "Website conversion copy is thin and the CTA hierarchy is unclear.",
    ],
    recommended_services: ["Local SEO"],
    outreach_subject: "Quick growth idea for Acme Dental",
    outreach_message: "There is a clear local visibility opportunity.",
    confidence: 0.84,
  },
  service_recommendations: [
    {
      public_id: "service_1",
      service_name: "Local SEO",
      rationale: "Discoverability is below target.",
      confidence: 0.81,
      rank_order: 1,
      created_at: "2026-04-29T10:15:00Z",
    },
  ],
};

describe("LeadAiAnalysisPanel", () => {
  it("renders AI-authored markdown and links to the lead assistant", () => {
    render(
      <MemoryRouter>
        <LeadAiAnalysisPanel
          snapshot={snapshot}
          leadId="lead_123"
          onGenerate={vi.fn()}
          generating={false}
          error={null}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("Strong fit")).toBeInTheDocument();
    expect(screen.getByText("high local trust")).toBeInTheDocument();
    expect(document.body).toHaveTextContent(
      "Prioritize local SEO because discoverability gaps are still visible.",
    );
    expect(
      screen.getByRole("link", { name: "Ask assistant about this lead" }),
    ).toHaveAttribute("href", "/app/assistant?leadId=lead_123");
    expect(screen.getByText("Local SEO")).toBeInTheDocument();
  });
});
