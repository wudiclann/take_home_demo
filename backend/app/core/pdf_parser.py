# PyMuPDF extraction: splits a PDF into chapters (preferring the embedded
# outline/TOC, falling back to a font-size heading heuristic) and paragraphs
# per chapter, ready for chunking.

from __future__ import annotations

import statistics
from dataclasses import dataclass

import fitz  # PyMuPDF

_HEADING_MAX_CHARS = 100
_HEADING_SIZE_RATIO = 1.25


@dataclass
class Paragraph:
    page: int  # 1-indexed
    text: str


@dataclass
class ParsedChapter:
    chapter_number: int
    title: str | None
    start_page: int
    end_page: int
    paragraphs: list[Paragraph]


@dataclass
class ParsedDocument:
    total_pages: int
    chapters: list[ParsedChapter]
    author: str | None = None


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _extract_paragraphs(doc: fitz.Document) -> list[Paragraph]:
    """Flatten every page's text blocks into paragraph-level units, in
    reading order, dropping blank blocks and bare page-number footers."""
    paragraphs: list[Paragraph] = []
    for page_index in range(doc.page_count):
        blocks = doc[page_index].get_text("blocks")
        blocks.sort(key=lambda b: (round(b[1]), b[0]))
        for block in blocks:
            text = _normalize(block[4])
            if not text or text.isdigit():
                continue
            paragraphs.append(Paragraph(page=page_index + 1, text=text))
    return paragraphs


def _find_paragraph_index(paragraphs: list[Paragraph], page: int, heading_text: str) -> int | None:
    for i, para in enumerate(paragraphs):
        if para.page == page and (para.text == heading_text or para.text.startswith(heading_text)):
            return i
    for i, para in enumerate(paragraphs):
        if para.page == page:
            return i
    return None


def _headings_from_toc(doc: fitz.Document, paragraphs: list[Paragraph]) -> list[tuple[str, int]]:
    """Match each top-level TOC entry to the paragraph it corresponds to."""
    headings: list[tuple[str, int]] = []
    for level, title, page in doc.get_toc():
        if level != 1:
            continue
        index = _find_paragraph_index(paragraphs, page, _normalize(title))
        if index is not None:
            headings.append((title, index))
    return headings


def _headings_from_font_size(doc: fitz.Document, paragraphs: list[Paragraph]) -> list[tuple[str, int]]:
    """Fallback for PDFs with no embedded outline: treat short, oversized,
    non-sentence-like lines as chapter headings."""
    sizes: list[float] = []
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span["text"].strip():
                        sizes.append(round(span["size"], 1))
    if not sizes:
        return []
    body_size = statistics.mode(sizes)
    threshold = body_size * _HEADING_SIZE_RATIO

    headings: list[tuple[str, int]] = []
    for page_index, page in enumerate(doc):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                line_text = _normalize("".join(s["text"] for s in spans))
                max_size = max(s["size"] for s in spans)
                is_heading_like = (
                    line_text
                    and len(line_text) <= _HEADING_MAX_CHARS
                    and max_size >= threshold
                    and not line_text.endswith((".", ",", ";"))
                )
                if is_heading_like:
                    index = _find_paragraph_index(paragraphs, page_index + 1, line_text)
                    if index is not None:
                        headings.append((line_text, index))
    return headings


def _build_chapters(
    paragraphs: list[Paragraph], headings: list[tuple[str, int]], total_pages: int
) -> list[ParsedChapter]:
    chapters: list[ParsedChapter] = []

    first_index = headings[0][1] if headings else len(paragraphs)
    if first_index > 0:
        front_matter = paragraphs[:first_index]
        chapters.append(
            ParsedChapter(
                chapter_number=0,
                title="Front Matter",
                start_page=front_matter[0].page,
                end_page=front_matter[-1].page,
                paragraphs=front_matter,
            )
        )

    for chapter_number, (title, start_index) in enumerate(headings, start=1):
        end_index = headings[chapter_number][1] if chapter_number < len(headings) else len(paragraphs)
        chapter_paragraphs = paragraphs[start_index:end_index]
        if not chapter_paragraphs:
            continue
        is_last = chapter_number == len(headings)
        chapters.append(
            ParsedChapter(
                chapter_number=chapter_number,
                title=_normalize(title),
                start_page=chapter_paragraphs[0].page,
                end_page=total_pages if is_last else chapter_paragraphs[-1].page,
                paragraphs=chapter_paragraphs,
            )
        )

    if not chapters:
        chapters.append(
            ParsedChapter(
                chapter_number=1,
                title=None,
                start_page=1,
                end_page=total_pages,
                paragraphs=paragraphs,
            )
        )

    return chapters


def parse_pdf(file_path: str) -> ParsedDocument:
    doc = fitz.open(file_path)
    try:
        total_pages = doc.page_count
        paragraphs = _extract_paragraphs(doc)

        headings = _headings_from_toc(doc, paragraphs)
        if not headings:
            headings = _headings_from_font_size(doc, paragraphs)

        chapters = _build_chapters(paragraphs, headings, total_pages)
        author = doc.metadata.get("author") or None
        return ParsedDocument(total_pages=total_pages, chapters=chapters, author=author)
    finally:
        doc.close()
