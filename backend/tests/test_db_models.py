from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Chapter, Document


def test_insert_and_read_document_with_chapter():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    document = Document(title="Attention Is All You Need", total_pages=11, status="ready")
    chapter = Chapter(
        document=document, chapter_number=1, title="Introduction", start_page=1, end_page=2
    )
    session.add(document)
    session.add(chapter)
    session.commit()

    fetched = session.query(Document).filter_by(title="Attention Is All You Need").one()
    assert fetched.status == "ready"
    assert len(fetched.chapters) == 1
    assert fetched.chapters[0].title == "Introduction"
    assert fetched.chapters[0].document_id == fetched.id

    session.close()
