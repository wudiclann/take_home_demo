# Structure-aware chunking: packs a chapter's paragraphs into chunks up to a
# target size (splitting oversized paragraphs on sentence boundaries), with a
# small character overlap carried into the next chunk -- not a fixed-size,
# no-overlap sliding window.

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.pdf_parser import Paragraph

TARGET_CHARS = 1200
OVERLAP_CHARS = 150
MAX_PARAGRAPH_CHARS = 1800

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Chunk:
    text: str
    start_page: int
    end_page: int


def _split_long_paragraph(paragraph: Paragraph) -> list[Paragraph]:
    if len(paragraph.text) <= MAX_PARAGRAPH_CHARS:
        return [paragraph]

    sentences = _SENTENCE_SPLIT_RE.split(paragraph.text)
    pieces: list[Paragraph] = []
    buffer = ""
    for sentence in sentences:
        if buffer and len(buffer) + len(sentence) + 1 > MAX_PARAGRAPH_CHARS:
            pieces.append(Paragraph(page=paragraph.page, text=buffer))
            buffer = sentence
        else:
            buffer = f"{buffer} {sentence}".strip()
    if buffer:
        pieces.append(Paragraph(page=paragraph.page, text=buffer))
    return pieces


def chunk_paragraphs(paragraphs: list[Paragraph]) -> list[Chunk]:
    units: list[Paragraph] = []
    for paragraph in paragraphs:
        units.extend(_split_long_paragraph(paragraph))

    chunks: list[Chunk] = []
    current: list[Paragraph] = []
    current_len = 0

    def flush_and_start_overlap() -> None:
        nonlocal current, current_len
        text = "\n\n".join(p.text for p in current)
        last_page = current[-1].page
        chunks.append(Chunk(text=text, start_page=current[0].page, end_page=last_page))
        overlap_text = text[-OVERLAP_CHARS:].strip()
        if overlap_text:
            current = [Paragraph(page=last_page, text=overlap_text)]
            current_len = len(overlap_text)
        else:
            current = []
            current_len = 0

    for unit in units:
        if current and current_len + len(unit.text) > TARGET_CHARS:
            flush_and_start_overlap()
        current.append(unit)
        current_len += len(unit.text)

    if current:
        chunks.append(
            Chunk(
                text="\n\n".join(p.text for p in current),
                start_page=current[0].page,
                end_page=current[-1].page,
            )
        )

    return chunks
