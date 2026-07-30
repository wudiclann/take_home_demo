# Orchestrates the ingestion background task: parse -> chunk -> embed ->
# persist, setting Document.status to 'ready' or 'failed'.

import uuid

from app.core.chunker import chunk_paragraphs
from app.core.embeddings import embed_texts
from app.core.pdf_parser import parse_pdf
from app.core.vector_store import add_chunks
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
            document.author = parsed.author

            chapter_rows: list[Chapter] = []
            chunk_rows: list[Chunk] = []
            chunk_texts: list[str] = []
            chunk_metadatas: list[dict] = []

            chunk_index = 0
            for parsed_chapter in parsed.chapters:
                chapter_id = str(uuid.uuid4())
                chapter_rows.append(
                    Chapter(
                        id=chapter_id,
                        document_id=document.id,
                        chapter_number=parsed_chapter.chapter_number,
                        title=parsed_chapter.title,
                        start_page=parsed_chapter.start_page,
                        end_page=parsed_chapter.end_page,
                    )
                )

                for chunk in chunk_paragraphs(parsed_chapter.paragraphs):
                    chunk_id = str(uuid.uuid4())
                    chunk_rows.append(
                        Chunk(
                            id=chunk_id,
                            document_id=document.id,
                            chapter_id=chapter_id,
                            chunk_index=chunk_index,
                            text=chunk.text,
                            start_page=chunk.start_page,
                            end_page=chunk.end_page,
                        )
                    )
                    chunk_texts.append(chunk.text)
                    chunk_metadatas.append(
                        {
                            "document_id": document.id,
                            "chapter_id": chapter_id,
                            "chunk_index": chunk_index,
                            "start_page": chunk.start_page,
                            "end_page": chunk.end_page,
                        }
                    )
                    chunk_index += 1

            # Embed and write to Chroma *before* committing SQLite, so a document
            # only ever reaches status='ready' if both stores actually succeeded.
            embeddings = embed_texts(chunk_texts)
            add_chunks(
                ids=[c.id for c in chunk_rows],
                texts=chunk_texts,
                embeddings=embeddings,
                metadatas=chunk_metadatas,
            )

            session.add_all(chapter_rows)
            session.add_all(chunk_rows)
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
