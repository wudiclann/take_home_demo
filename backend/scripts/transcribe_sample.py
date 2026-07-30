"""Manual sanity check: synthesizes a short sample sentence via TTS (so no
external audio fixture is needed), sends it to POST /transcribe, and prints
the resulting transcript so it can be eyeballed against the original text.

Usage:
    ./venv/bin/python scripts/transcribe_sample.py
    ./venv/bin/python scripts/transcribe_sample.py "Some other sentence to speak and transcribe."
"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_SENTENCE = "The quick brown fox jumps over the lazy dog."


def main() -> None:
    from fastapi.testclient import TestClient

    from app.core.tts import synthesize_speech
    from app.main import app

    text = " ".join(sys.argv[1:]) or DEFAULT_SENTENCE
    print(f"Original text: {text!r}")

    audio_path = synthesize_speech(text, f"sample-{uuid.uuid4()}")
    print(f"Generated sample audio at: {audio_path}")

    client = TestClient(app)
    with open(audio_path, "rb") as f:
        response = client.post("/transcribe", files={"file": ("sample.mp3", f, "audio/mpeg")})
    response.raise_for_status()

    print(f"Transcript: {response.json()['text']!r}")


if __name__ == "__main__":
    main()
