"""Real (no-mock) tests for GET /settings, PUT /settings/openai-key, and the
"no OpenAI key configured" gate on the endpoints that call OpenAI.

The isolated test .env (see conftest.py's isolated_app_storage) is a copy of
the real dev .env, so it starts out with a real, working key -- every test
here that mutates it restores the original key in a `finally` block so later
tests in the suite (which make real OpenAI calls) keep working.
"""


def test_get_settings_reports_key_already_configured(client):
    response = client.get("/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["is_openai_key_configured"] is True

    from app.core.api_key import MASKED_KEY

    assert body["openai_api_key_masked"] == MASKED_KEY
    assert "sk-" in body["openai_api_key_masked"]


def test_get_settings_reports_voice_defaults(client):
    from app.core.voice_settings import AVAILABLE_VOICES

    response = client.get("/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["tts_voice"] in AVAILABLE_VOICES
    assert body["tts_speed"] > 0
    assert set(body["available_voices"]) == set(AVAILABLE_VOICES)


def test_update_voice_settings_rejects_invalid_voice(client):
    response = client.put("/settings/voice", json={"voice": "not-a-real-voice", "speed": 1.0})
    assert response.status_code == 400


def test_update_voice_settings_rejects_out_of_range_speed(client):
    response = client.put("/settings/voice", json={"voice": "nova", "speed": 10.0})
    assert response.status_code == 400


def test_update_voice_settings_persists_and_takes_effect_without_restart(client):
    from app.config import get_settings
    from app.core.voice_settings import save_speed, save_voice

    original_voice = get_settings().tts_voice
    original_speed = get_settings().tts_speed
    try:
        response = client.put("/settings/voice", json={"voice": "onyx", "speed": 1.5})
        assert response.status_code == 200
        body = response.json()
        assert body["tts_voice"] == "onyx"
        assert body["tts_speed"] == 1.5

        # @lru_cache'd get_settings() -- confirms the change is visible immediately.
        assert get_settings().tts_voice == "onyx"
        assert get_settings().tts_speed == 1.5
    finally:
        save_voice(original_voice)
        save_speed(original_speed)


def test_update_openai_key_rejects_invalid_format(client):
    response = client.put("/settings/openai-key", json={"api_key": "not-a-real-key"})
    assert response.status_code == 400


def test_update_openai_key_persists_and_takes_effect_without_restart(client):
    from app.config import ENV_FILE, get_settings

    original_key = get_settings().openai_api_key
    try:
        new_key = "sk-" + "a" * 40
        response = client.put("/settings/openai-key", json={"api_key": new_key})
        assert response.status_code == 200
        body = response.json()
        assert body["is_openai_key_configured"] is True

        assert f"OPENAI_API_KEY={new_key}" in ENV_FILE.read_text()
        # get_settings is @lru_cache'd -- confirms save_key() actually
        # invalidated it rather than requiring a server restart to see the change.
        assert get_settings().openai_api_key == new_key
    finally:
        restore = client.put("/settings/openai-key", json={"api_key": original_key})
        assert restore.status_code == 200
        assert get_settings().openai_api_key == original_key


def test_delete_openai_key_clears_it(client):
    from app.config import get_settings

    original_key = get_settings().openai_api_key
    try:
        response = client.delete("/settings/openai-key")
        assert response.status_code == 200
        body = response.json()
        assert body["is_openai_key_configured"] is False
        assert body["openai_api_key_masked"] is None
        # Confirms the clear takes effect immediately, same as a save does.
        assert get_settings().openai_api_key == ""
    finally:
        restore = client.put("/settings/openai-key", json={"api_key": original_key})
        assert restore.status_code == 200
        assert get_settings().openai_api_key == original_key


def test_upload_and_chat_blocked_when_key_not_configured(client, sample_document_id):
    from app.config import get_settings

    original_key = get_settings().openai_api_key
    try:
        assert client.delete("/settings/openai-key").status_code == 200

        upload_response = client.post(
            "/documents/upload",
            files={"file": ("x.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
        )
        assert upload_response.status_code == 400
        assert "API key" in upload_response.json()["detail"]

        conversation_id = client.post(
            "/conversations", json={"document_id": sample_document_id}
        ).json()["id"]

        chat_response = client.post(
            "/chat", json={"conversation_id": conversation_id, "question": "test"}
        )
        assert chat_response.status_code == 400
        assert "API key" in chat_response.json()["detail"]

        transcribe_response = client.post(
            "/transcribe", files={"file": ("q.mp3", b"not-real-audio", "audio/mpeg")}
        )
        assert transcribe_response.status_code == 400
    finally:
        restore = client.put("/settings/openai-key", json={"api_key": original_key})
        assert restore.status_code == 200
        assert get_settings().openai_api_key == original_key
