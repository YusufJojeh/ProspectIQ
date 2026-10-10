/** `review_count_changed` -> `Review count changed`. Fallback for vocabulary the UI has no string for. */
export function humanizeKey(key: string): string {
  const spaced = key.replace(/[_-]+/g, " ").trim();
  return spaced.length === 0 ? key : spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function formatPercent01(value: number): string {
  const clamped = Math.min(1, Math.max(0, Number.isFinite(value) ? value : 0));
  return `${Math.round(clamped * 100)}%`;
}

/** Locale-aware short date-time; returns an empty string for an unparseable input. */
export function formatWhen(value: string | null | undefined, locale: string): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

/** Score movement label, or null when either side is unknown. */
export function scoreDelta(before: number | null, after: number | null): number | null {
  if (before === null || after === null) return null;
  return Math.round((after - before) * 10) / 10;
}
