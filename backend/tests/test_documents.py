"""Real (no-mock) tests for document listing/detail endpoints: GET /documents,
GET /documents/{id}/chapters, GET /documents/{id}/pages/{n}, and
GET /documents/{id}/conversation (get-or-create).
"""


def test_list_documents_includes_sample(client, sample_document_id):
    response = client.get("/documents")
    assert response.status_code == 200
    matching = [d for d in response.json() if d["id"] == sample_document_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "ready"
    assert matching[0]["total_pages"] == 15


def test_list_chapters_returns_ordered_chapters(client, sample_document_id):
    response = client.get(f"/documents/{sample_document_id}/chapters")
    assert response.status_code == 200
    chapters = response.json()
    assert 5 <= len(chapters) <= 12
    numbers = [c["chapter_number"] for c in chapters]
    assert numbers == sorted(numbers)
    titles = " ".join(c["title"] or "" for c in chapters)
    assert "Introduction" in titles


def test_get_document_page_image_returns_png(client, sample_document_id):
    response = client.get(f"/documents/{sample_document_id}/pages/1")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_get_document_page_image_out_of_range(client, sample_document_id):
    response = client.get(f"/documents/{sample_document_id}/pages/9999")
    assert response.status_code == 404


def test_get_or_create_conversation_is_idempotent(client, sample_document_id):
    first = client.get(f"/documents/{sample_document_id}/conversation")
    assert first.status_code == 200
    second = client.get(f"/documents/{sample_document_id}/conversation")
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
