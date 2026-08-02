"""Tests for the slowapi rate limits on POST /documents/upload, /chat, /ask.

Each test drives the endpoint with a cheap, fast-failing request (invalid file,
nonexistent conversation_id) so it never reaches real OpenAI calls -- slowapi
counts a call against the limit as soon as the endpoint is entered, before the
handler body runs, so these still exercise the limiter correctly. limiter.reset()
brackets each test so it's independent of how many real requests earlier tests
in the suite already made against the same in-memory limiter state, and so it
doesn't leave the limiter primed for tests that run after it.
"""


def test_upload_rate_limited_after_too_many_requests(client):
    from app.core.rate_limit import limiter

    limiter.reset()
    try:
        for _ in range(5):  # matches the 5/minute limit on /documents/upload
            response = client.post(
                "/documents/upload",
                files={"file": ("not-a-pdf.txt", b"nope", "text/plain")},
            )
            assert response.status_code == 400

        response = client.post(
            "/documents/upload",
            files={"file": ("not-a-pdf.txt", b"nope", "text/plain")},
        )
        assert response.status_code == 429
    finally:
        limiter.reset()


def test_chat_rate_limited_after_too_many_requests(client):
    from app.core.rate_limit import limiter

    limiter.reset()
    try:
        for _ in range(20):  # matches the 20/minute limit on /chat
            response = client.post(
                "/chat", json={"conversation_id": "does-not-exist", "question": "x"}
            )
            assert response.status_code == 404

        response = client.post(
            "/chat", json={"conversation_id": "does-not-exist", "question": "x"}
        )
        assert response.status_code == 429
    finally:
        limiter.reset()


def test_ask_rate_limited_after_too_many_requests(client):
    from app.core.rate_limit import limiter

    limiter.reset()
    try:
        for _ in range(20):  # matches the 20/minute limit on /ask
            response = client.post(
                "/ask",
                data={"conversation_id": "does-not-exist"},
                files={"file": ("q.mp3", b"not-real-audio", "audio/mpeg")},
            )
            assert response.status_code == 404

        response = client.post(
            "/ask",
            data={"conversation_id": "does-not-exist"},
            files={"file": ("q.mp3", b"not-real-audio", "audio/mpeg")},
        )
        assert response.status_code == 429
    finally:
        limiter.reset()
