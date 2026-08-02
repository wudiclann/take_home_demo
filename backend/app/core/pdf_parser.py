# PyMuPDF extraction: splits a PDF into chapters (preferring the embedded
# outline/TOC, falling back to a font-size heading heuristic) and paragraphs
# per chapter, ready for chunking.
#
# 基于 PyMuPDF 的 PDF 解析模块：将 PDF 拆分为多个章节（优先使用 PDF 自带的
# 目录/大纲，若没有则退化为按字号识别标题的启发式方法），并提取每章的段落，
# 为后续分块（chunking）做准备。

from __future__ import annotations

import statistics
from dataclasses import dataclass

import fitz  # PyMuPDF

_HEADING_MAX_CHARS = 100
_HEADING_SIZE_RATIO = 1.25


@dataclass
class Paragraph:
    """One paragraph of extracted text and the page it came from.
    一个提取出的段落及其所在页码。"""

    page: int  # 1-indexed / 页码从 1 开始
    text: str


@dataclass
class ParsedChapter:
    """One chapter: its title, page range, and the paragraphs inside it.
    一个章节：标题、页码范围，以及章节内的段落列表。"""

    chapter_number: int
    title: str | None
    start_page: int
    end_page: int
    paragraphs: list[Paragraph]


@dataclass
class ParsedDocument:
    """The whole parsed PDF: total page count plus its list of chapters.
    整份已解析的 PDF：总页数，以及章节列表。"""

    total_pages: int
    chapters: list[ParsedChapter]
    author: str | None = None


def _normalize(text: str) -> str:
    """Collapses whitespace/newlines down to single spaces.
    将空白字符与换行符压缩为单个空格。"""
    return " ".join(text.split())


def _extract_paragraphs(doc: fitz.Document) -> list[Paragraph]:
    """Flatten every page's text blocks into paragraph-level units, in
    reading order, dropping blank blocks and bare page-number footers.

    将每一页的文本块按阅读顺序展开为段落级别的单元，
    并丢弃空白文本块和纯数字的页码页脚。
    """
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
    """Finds the paragraph a heading corresponds to: first tries an exact/prefix
    text match on that page, then falls back to that page's first paragraph.
    查找某个标题对应的段落：先在该页尝试精确或前缀文本匹配，
    找不到时退回该页的第一个段落。"""
    for i, para in enumerate(paragraphs):
        if para.page == page and (para.text == heading_text or para.text.startswith(heading_text)):
            return i
    for i, para in enumerate(paragraphs):
        if para.page == page:
            return i
    return None


def _headings_from_toc(doc: fitz.Document, paragraphs: list[Paragraph]) -> list[tuple[str, int]]:
    """Match each top-level TOC entry to the paragraph it corresponds to.
    将 PDF 目录（TOC）中每一个顶层条目匹配到其对应的段落。"""
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
    non-sentence-like lines as chapter headings.

    当 PDF 没有内嵌目录时的兜底方案：把字号明显偏大、较短、
    且不像完整句子的行当作章节标题。
    """
    sizes: list[float] = []
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span["text"].strip():
                        sizes.append(round(span["size"], 1))
    if not sizes:
        return []
    body_size = statistics.mode(sizes)  # the most common font size = normal body text / 出现最频繁的字号即正文字号
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
    """Slices the flat paragraph list into chapters at each heading's position,
    plus a "Front Matter" chapter for anything before the first heading, and a
    single-chapter fallback if no headings were found at all.

    根据每个标题的位置，把整份段落列表切分成多个章节；标题之前的内容归入
    "Front Matter"（前置内容）章节；如果完全没有识别到任何标题，
    则整本书作为单一章节处理。
    """
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
    """Entry point: opens a PDF file and returns it fully parsed into
    chapters and paragraphs, preferring the embedded TOC over the font-size
    heuristic when both are available.

    入口函数：打开一个 PDF 文件，将其完整解析为章节和段落；
    如果 PDF 自带目录，优先使用目录，否则才使用按字号识别的启发式方法。
    """
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
