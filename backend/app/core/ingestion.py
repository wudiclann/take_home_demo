# Orchestrates the ingestion background task: parse -> chunk -> persist,
# setting Document.status to 'ready' or 'failed'.

from app.core.chunker import chunk_paragraphs
from app.core.pdf_parser import parse_pdf
from app.db.models import Chapter, Chunk, Document
from app.db.session import SessionLocal


def process_document(document_id: str) -> None:
    session = SessionLocal()
    try:
        document = session.get(Document, document_id)
        if document is None:
            return
        try:
            parsed = parse_pdf(document.file_path)
            document.total_pages = parsed.total_pages

            chunk_index = 0
            for parsed_chapter in parsed.chapters:
                chapter = Chapter(
                    document_id=document.id,
                    chapter_number=parsed_chapter.chapter_number,
                    title=parsed_chapter.title,
                    start_page=parsed_chapter.start_page,
                    end_page=parsed_chapter.end_page,
                )
                session.add(chapter)
                session.flush()  # populate chapter.id for the chunks below

                for chunk in chunk_paragraphs(parsed_chapter.paragraphs):
                    session.add(
                        Chunk(
                            document_id=document.id,
                            chapter_id=chapter.id,
                            chunk_index=chunk_index,
                            text=chunk.text,
                            start_page=chunk.start_page,
                            end_page=chunk.end_page,
                        )
                    )
                    chunk_index += 1

            document.status = "ready"
            session.commit()
        except Exception as exc:
            session.rollback()
            document = session.get(Document, document_id)
            if document is not None:
                document.status = "failed"
                document.error_message = str(exc)
                session.commit()
    finally:
        session.close()
