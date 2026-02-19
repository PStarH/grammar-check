from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TextChunk:
    start: int
    end: int
    text: str


def _paragraph_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    start = 0
    for para in text.split("\n\n"):
        end = start + len(para)
        if para.strip():
            ranges.append((start, end))
        start = end + 2
    return ranges


def chunk_plain_text(text: str, max_chunk_chars: int) -> list[TextChunk]:
    if len(text) <= max_chunk_chars:
        return [TextChunk(start=0, end=len(text), text=text)] if text else []

    chunks: list[TextChunk] = []
    for p_start, p_end in _paragraph_ranges(text):
        paragraph = text[p_start:p_end]
        if len(paragraph) <= max_chunk_chars:
            chunks.append(TextChunk(start=p_start, end=p_end, text=paragraph))
            continue
        cursor = 0
        while cursor < len(paragraph):
            limit = min(cursor + max_chunk_chars, len(paragraph))
            split = paragraph.rfind(". ", cursor, limit)
            if split <= cursor:
                split = limit
            else:
                split += 1
            chunk_start = p_start + cursor
            chunk_end = p_start + split
            chunks.append(
                TextChunk(start=chunk_start, end=chunk_end, text=text[chunk_start:chunk_end])
            )
            cursor = split
    return [c for c in chunks if c.text.strip()]
