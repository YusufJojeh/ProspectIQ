/** Mirrors `knowledge_max_document_chars` (server default). The server remains the authority. */
export const MAX_DOCUMENT_CHARS = 400_000;

/** Plain-text formats only: the backend ingests text, not binary documents. */
export const ACCEPTED_EXTENSIONS = [".txt", ".md", ".markdown", ".csv"] as const;

export type FileReadFailure = "type" | "empty" | "tooLarge" | "unreadable";

export type FileReadResult =
  | { ok: true; text: string; suggestedTitle: string }
  | { ok: false; reason: FileReadFailure };

export function hasAcceptedExtension(name: string): boolean {
  const lower = name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

/** `Q3 pricing-guide.v2.md` -> `Q3 pricing guide v2` */
export function titleFromFileName(name: string): string {
  const withoutExt = name.replace(/\.[^.]+$/, "");
  return withoutExt.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim() || name;
}

export async function readKnowledgeFile(file: File): Promise<FileReadResult> {
  if (!hasAcceptedExtension(file.name)) return { ok: false, reason: "type" };
  // A UTF-8 character is at least one byte, so this cheap check never rejects a valid file
  // and avoids reading something enormous into memory.
  if (file.size > MAX_DOCUMENT_CHARS * 4) return { ok: false, reason: "tooLarge" };
  let text: string;
  try {
    text = await file.text();
  } catch {
    return { ok: false, reason: "unreadable" };
  }
  const trimmed = text.replace(/^\uFEFF/, "");
  if (trimmed.trim().length === 0) return { ok: false, reason: "empty" };
  if (trimmed.length > MAX_DOCUMENT_CHARS) return { ok: false, reason: "tooLarge" };
  return { ok: true, text: trimmed, suggestedTitle: titleFromFileName(file.name) };
}
