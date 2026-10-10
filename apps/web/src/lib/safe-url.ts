/**
 * Returns the URL only when it is an http(s) URL, otherwise null.
 *
 * Evidence sources and knowledge excerpts contain URLs that originate from
 * crawled pages or model output. `javascript:`, `data:` and similar schemes
 * must never reach an `href`.
 */
export function safeHttpUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value.trim());
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

/** Hostname for display, or null when the URL is unsafe or malformed. */
export function displayHost(value: string | null | undefined): string | null {
  const safe = safeHttpUrl(value);
  return safe ? new URL(safe).hostname.replace(/^www\./, "") : null;
}
