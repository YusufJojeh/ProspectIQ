import { describe, expect, it } from "vitest";

import type { AuditFinding } from "@/types/proposals";

import { auditCoverEmail, findingText, opportunityCount, ownFigures } from "./audit-labels";

const findings: AuditFinding[] = [
  { key: "website", status: "missing", values: { peer_pct: 80 } },
  { key: "rating", status: "improve", values: { rating: 4.2, peer_median: 4.7 } },
  { key: "reviews", status: "good", values: { count: 140, peer_median: 90 } },
];

describe("presence audit wording", () => {
  it("quotes the business's numbers next to the local median", () => {
    expect(findingText(findings[1]!, "en").title).toBe("4.2★ rating vs 4.7★ nearby");
    expect(findingText(findings[0]!, "en").detail).toContain("80% of similar businesses nearby");
  });

  it("words the same finding in Arabic", () => {
    expect(findingText(findings[0]!, "ar").title).toBe("لم نجد موقعًا إلكترونيًا");
  });

  it("counts opportunities and reads the business's own figures", () => {
    expect(opportunityCount(findings)).toBe(2);
    expect(ownFigures(findings)).toEqual({ rating: 4.2, reviews: 140, website: false });
  });

  it("lists only the opportunities in the cover email", () => {
    const email = auditCoverEmail({ language: "en", companyName: "Acme Dental", findings, senderName: "Bright Co" });
    expect(email).toContain("Subject: A quick online presence check for Acme Dental");
    expect(email).toContain("- No website found");
    expect(email).not.toContain("140 reviews");
    expect(email.trimEnd().endsWith("Bright Co")).toBe(true);
  });
});
