const ARABIC_TEXT_PATTERN = /[\u0600-\u06ff]/;
const BILINGUAL_LABEL_PATTERN =
  /(العربية|Arabic|English|الإنجليزية)\s*:/gi;

type AnalysisLanguage = "ar" | "en";

export function resolveAnalysisLanguage(language?: string): AnalysisLanguage {
  return language?.toLowerCase().startsWith("ar") ? "ar" : "en";
}

export function localizeAnalysisText(
  value: string,
  language?: string,
): string {
  const preferredLanguage = resolveAnalysisLanguage(language);
  const trimmed = value.trim();
  if (!trimmed) return trimmed;

  const labeled = extractLabeledSection(trimmed, preferredLanguage);
  if (labeled) return labeled;

  const slashSeparated = extractSlashSeparatedSection(
    trimmed,
    preferredLanguage,
  );
  return slashSeparated || trimmed;
}

export function localizeAnalysisItems(
  items: string[],
  language?: string,
): string[] {
  return items.map((item) => localizeAnalysisText(item, language));
}

function extractLabeledSection(
  value: string,
  language: AnalysisLanguage,
): string | null {
  const matches = Array.from(value.matchAll(BILINGUAL_LABEL_PATTERN));
  if (!matches.length) return null;

  const sections = matches
    .map((match, index) => {
      const label = match[1]?.toLowerCase();
      const sectionLanguage: AnalysisLanguage =
        label === "english" ? "en" : "ar";
      const start = (match.index ?? 0) + match[0].length;
      const end =
        index + 1 < matches.length ? (matches[index + 1].index ?? value.length) : value.length;
      return {
        language: sectionLanguage,
        text: value.slice(start, end).trim(),
      };
    })
    .filter((section) => section.text.length > 0);

  return (
    sections.find((section) => section.language === language)?.text ??
    sections[0]?.text ??
    null
  );
}

function extractSlashSeparatedSection(
  value: string,
  language: AnalysisLanguage,
): string | null {
  const parts = value
    .split(/\s+\/\s+/)
    .map((part) => part.trim())
    .filter(Boolean);
  if (parts.length < 2) return null;

  const preferred = parts.find((part) =>
    language === "ar"
      ? ARABIC_TEXT_PATTERN.test(part)
      : !ARABIC_TEXT_PATTERN.test(part),
  );
  return preferred ?? null;
}
