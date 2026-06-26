import { describe, expect, it } from "vitest";
import {
  localizeAnalysisItems,
  localizeAnalysisText,
} from "@/lib/localized-analysis";

describe("localized analysis presentation", () => {
  it("selects only the requested labeled language", () => {
    const text =
      "العربية: تحليل التسجيل المحلي يظهر جودة بيانات جيدة.\nEnglish: Local listing analysis shows good data quality.";

    expect(localizeAnalysisText(text, "ar")).toBe(
      "تحليل التسجيل المحلي يظهر جودة بيانات جيدة.",
    );
    expect(localizeAnalysisText(text, "en")).toBe(
      "Local listing analysis shows good data quality.",
    );
  });

  it("selects list item segments by language even when order varies", () => {
    const items = [
      "Improve official website discoverability / تحسين ظهور الموقع الرسمي",
      "إنشاء مخطط معرفة للعلامة التجارية / Create a brand knowledge graph",
    ];

    expect(localizeAnalysisItems(items, "ar")).toEqual([
      "تحسين ظهور الموقع الرسمي",
      "إنشاء مخطط معرفة للعلامة التجارية",
    ]);
    expect(localizeAnalysisItems(items, "en")).toEqual([
      "Improve official website discoverability",
      "Create a brand knowledge graph",
    ]);
  });
});
