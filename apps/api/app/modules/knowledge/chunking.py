from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

# --- Semantic-safe chunking --------------------------------------------
#
# The goal is not "cut every N characters". It is: never let a chunk
# boundary destroy which service or which case study a passage belongs to.
# So the text is split on structure first (headings, then blank-line
# paragraphs, then sentences), and each resulting chunk carries the heading
# it sat under. A chunk that says "we cut no-show rates by a third" is
# useless without "Case study: Riyadh dental clinic" attached to it.

_HEADING_RE = re.compile(
    r"^(?:#{1,6}\s+(?P<hash>.+?)\s*|(?P<bare>[A-Z][^\n]{2,80}?)\s*[:：]|\s*(?P<setext>[^\n]{3,80})\n[=-]{3,})$"
)
_MD_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")
_WHITESPACE_RE = re.compile(r"[ \t]+")
_BLANKLINES_RE = re.compile(r"\n{3,}")
#: Control characters (other than tab/newline) are stripped: they carry no
#: meaning and are a classic way to smuggle hidden text past a reviewer.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
#: Zero-width and bidirectional-override characters, likewise.
_INVISIBLE_RE = re.compile(r"[​-‏‪-‮⁠-⁤﻿]")


@dataclass(frozen=True, slots=True)
class Chunk:
    index: int
    content: str
    section: str | None
    token_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


def sanitize_text(raw: str) -> str:
    """Normalize and de-fang document text before it is stored.

    Sanitizing is not a security control on its own -- retrieved knowledge
    is treated as untrusted data regardless (see agents.untrusted). It is
    here so that what a reviewer reads in the UI is what the model receives:
    no invisible characters, no control bytes, no exotic Unicode forms that
    render as one thing and tokenize as another.
    """
    text = unicodedata.normalize("NFKC", raw)
    text = _CONTROL_RE.sub("", text)
    text = _INVISIBLE_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RE.sub(" ", text)
    text = _BLANKLINES_RE.sub("\n\n", text)
    return text.strip()


def approximate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _split_sections(text: str) -> list[tuple[str | None, str]]:
    """Split into (heading, body) pairs on Markdown-style headings.

    Text before the first heading keeps `None` as its section, so an
    unstructured document still chunks correctly.
    """
    sections: list[tuple[str | None, str]] = []
    current_heading: str | None = None
    buffer: list[str] = []
    for line in text.split("\n"):
        match = _MD_HEADING_RE.match(line.strip())
        if match:
            if buffer:
                sections.append((current_heading, "\n".join(buffer).strip()))
                buffer = []
            current_heading = match.group(1).strip()
            continue
        buffer.append(line)
    if buffer:
        sections.append((current_heading, "\n".join(buffer).strip()))
    return [(heading, body) for heading, body in sections if body]


def _split_paragraphs(body: str) -> list[str]:
    return [para.strip() for para in body.split("\n\n") if para.strip()]


def _split_long_paragraph(paragraph: str, max_chars: int) -> list[str]:
    """Break a paragraph that exceeds the hard cap, on sentence boundaries
    where possible and only on raw length as a last resort."""
    if len(paragraph) <= max_chars:
        return [paragraph]
    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_RE.split(paragraph):
        if not sentence:
            continue
        if len(sentence) > max_chars:
            if current:
                pieces.append(current.strip())
                current = ""
            for start in range(0, len(sentence), max_chars):
                pieces.append(sentence[start : start + max_chars].strip())
            continue
        if len(current) + len(sentence) + 1 > max_chars:
            pieces.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current.strip():
        pieces.append(current.strip())
    return [piece for piece in pieces if piece]


def chunk_document(
    text: str,
    *,
    target_chars: int,
    overlap_chars: int,
    max_chars: int,
    max_chunks: int,
    base_metadata: dict[str, Any] | None = None,
) -> list[Chunk]:
    """Chunk one document's text, preserving section context.

    Chunks accumulate whole paragraphs until `target_chars` is reached, so
    a short service description stays in one piece rather than being split
    mid-definition. `overlap_chars` of trailing text is carried into the
    next chunk so a sentence spanning a boundary is retrievable from either
    side.
    """
    cleaned = sanitize_text(text)
    if not cleaned:
        return []

    metadata = dict(base_metadata or {})
    chunks: list[Chunk] = []

    for heading, body in _split_sections(cleaned):
        current = ""
        for paragraph in _split_paragraphs(body):
            for piece in _split_long_paragraph(paragraph, max_chars):
                candidate = f"{current}\n\n{piece}".strip() if current else piece
                if len(candidate) <= target_chars or not current:
                    current = candidate
                    continue
                chunks.append(_make_chunk(len(chunks), current, heading, metadata))
                if len(chunks) >= max_chunks:
                    return chunks
                tail = current[-overlap_chars:] if overlap_chars else ""
                current = f"{tail}\n\n{piece}".strip() if tail else piece
        if current.strip():
            chunks.append(_make_chunk(len(chunks), current, heading, metadata))
            if len(chunks) >= max_chunks:
                return chunks

    return chunks


def _make_chunk(
    index: int, content: str, heading: str | None, metadata: dict[str, Any]
) -> Chunk:
    body = content.strip()
    # The heading is prepended to the embedded text as well as stored: a
    # passage about "reduced no-shows" should match a query about
    # "appointment automation" through its own section title.
    embedded = f"{heading}\n\n{body}" if heading else body
    chunk_metadata = dict(metadata)
    if heading:
        chunk_metadata["section"] = heading
    return Chunk(
        index=index,
        content=embedded,
        section=heading,
        token_count=approximate_tokens(embedded),
        metadata=chunk_metadata,
    )


__all__ = ["Chunk", "approximate_tokens", "chunk_document", "sanitize_text"]
