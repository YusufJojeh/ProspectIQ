/**
 * Money on the wire is integer minor units; people type and read decimals.
 * These two functions are the only place the two meet.
 */

/** "1,500.00" style, independent of UI locale so documents read the same everywhere. */
export function formatMinor(amountMinor: number | null | undefined): string {
  if (amountMinor === null || amountMinor === undefined) return "—";
  const negative = amountMinor < 0;
  const abs = Math.abs(Math.trunc(amountMinor));
  const whole = Math.floor(abs / 100)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const cents = (abs % 100).toString().padStart(2, "0");
  return `${negative ? "-" : ""}${whole}.${cents}`;
}

export function formatMoney(currency: string, amountMinor: number | null | undefined): string {
  return amountMinor === null || amountMinor === undefined
    ? "—"
    : `${currency} ${formatMinor(amountMinor)}`;
}

/**
 * Parses what a person typed ("7,500", "7500.5", " 12 000 ") into minor
 * units. Returns null for empty input and undefined for anything that is
 * not a non-negative amount with at most two decimals.
 */
export function parseMinor(input: string): number | null | undefined {
  const cleaned = input.replace(/[\s,]/g, "");
  if (cleaned === "") return null;
  const match = /^(\d{1,10})(?:\.(\d{1,2}))?$/.exec(cleaned);
  if (!match) return undefined;
  const whole = Number(match[1]);
  const fraction = Number((match[2] ?? "").padEnd(2, "0"));
  return whole * 100 + fraction;
}

/** Minor units back to an editable string ("1500.00" -> "1500.00", null -> ""). */
export function minorToInput(amountMinor: number | null): string {
  if (amountMinor === null) return "";
  const whole = Math.floor(amountMinor / 100);
  const cents = amountMinor % 100;
  return cents === 0 ? String(whole) : `${whole}.${cents.toString().padStart(2, "0")}`;
}
