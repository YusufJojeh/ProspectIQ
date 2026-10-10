import { describe, expect, it } from "vitest";

import {
  MAX_DOCUMENT_CHARS,
  hasAcceptedExtension,
  readKnowledgeFile,
  titleFromFileName,
} from "./read-knowledge-file";

function file(name: string, body: string): File {
  return new File([body], name, { type: "text/plain" });
}

describe("readKnowledgeFile", () => {
  it("accepts text formats and derives a title", async () => {
    const result = await readKnowledgeFile(file("Q3_pricing-guide.md", "﻿# Pricing\n\nText"));
    expect(result).toEqual({ ok: true, text: "# Pricing\n\nText", suggestedTitle: "Q3 pricing guide" });
  });

  it("rejects binary document types instead of ingesting garbage", async () => {
    expect(hasAcceptedExtension("deck.pdf")).toBe(false);
    expect(await readKnowledgeFile(file("deck.pdf", "%PDF"))).toEqual({ ok: false, reason: "type" });
    expect(await readKnowledgeFile(file("notes.docx", "x"))).toEqual({ ok: false, reason: "type" });
  });

  it("rejects empty and oversize content", async () => {
    expect(await readKnowledgeFile(file("a.txt", "  \n "))).toEqual({ ok: false, reason: "empty" });
    expect(await readKnowledgeFile(file("a.txt", "x".repeat(MAX_DOCUMENT_CHARS + 1)))).toEqual({
      ok: false,
      reason: "tooLarge",
    });
  });

  it("falls back to the raw name when nothing is left after cleanup", () => {
    expect(titleFromFileName(".md")).toBe(".md");
  });
});
