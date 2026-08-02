# Structure-aware chunking: packs a chapter's paragraphs into chunks up to a
# target size (splitting oversized paragraphs on sentence boundaries), with a
# small character overlap carried into the next chunk -- not a fixed-size,
# no-overlap sliding window.
#
# 结构感知分块模块：把一个章节内的段落打包成大小接近目标值的文本块
# （过长的段落会按句子边界切开），相邻块之间保留少量字符重叠——
# 而不是简单的、无重叠的固定长度滑动窗口。

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
    """One retrieval-ready chunk of text and the page range it spans.
    一个可用于检索的文本块，以及它跨越的页码范围。"""

    text: str
    start_page: int
    end_page: int


def _split_long_paragraph(paragraph: Paragraph) -> list[Paragraph]:
    """Splits a paragraph longer than MAX_PARAGRAPH_CHARS into smaller pieces
    on sentence boundaries, so one giant paragraph can't dominate a whole chunk.
    把超过 MAX_PARAGRAPH_CHARS 的段落按句子边界切成更小的片段，
    避免单个超长段落独占整个文本块。"""
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
    """Packs a chapter's paragraphs into chunks around TARGET_CHARS long. When
    a chunk fills up, the tail of it (OVERLAP_CHARS) is carried over as the
    start of the next chunk, so a fact split across a chunk boundary is still
    findable from either side.

    把一个章节的段落打包成长度接近 TARGET_CHARS 的文本块。当一个块被填满时，
    它末尾的一部分内容（OVERLAP_CHARS 个字符）会被带入下一个块的开头，
    这样即使某个知识点正好落在块的边界上，从前后两个块都能检索到它。
    """
    units: list[Paragraph] = []
    for paragraph in paragraphs:
        units.extend(_split_long_paragraph(paragraph))

    chunks: list[Chunk] = []
    current: list[Paragraph] = []
    current_len = 0

    def flush_and_start_overlap() -> None:
        """Closes out the current chunk and seeds the next one with its
        trailing OVERLAP_CHARS of text.
        结束当前文本块，并用其末尾 OVERLAP_CHARS 个字符作为下一个块的起始内容。"""
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
