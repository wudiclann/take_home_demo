"""Manual sanity check: synthesizes a sample sentence to speech via the OpenAI
TTS API and saves it to disk so it can be played back and listened to.

Usage:
    ./venv/bin/python scripts/synthesize_sample.py
    ./venv/bin/python scripts/synthesize_sample.py "Some other sentence to speak."
"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.tts import synthesize_speech  # noqa: E402

DEFAULT_SENTENCE = (
    "Hello! This is a sample sentence synthesized by the text to speech pipeline. "
    "If you can hear this clearly, the TTS integration is working."
)


def main() -> None:
    text = " ".join(sys.argv[1:]) or DEFAULT_SENTENCE
    message_id = f"sample-{uuid.uuid4()}"
    path = synthesize_speech(text, message_id)
    print(f"Text: {text!r}")
    print(f"Saved audio to: {path}")
    print(f"Play it back with: afplay {path}")


if __name__ == "__main__":
    main()
