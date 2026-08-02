# Voice PDF Book Q&A

Upload a PDF book and have a spoken conversation with it: ask a question by voice (or type
it), and get a spoken, book-grounded answer back — with citations to the actual pages the
answer came from.

```
Mic input → ASR → hybrid RAG (retrieve from the book + LLM) → TTS → audio playback
```

## What this actually is

This started as a take-home exercise: build a web app where a user uploads a PDF book and has a
spoken conversation with it, grounded in that book's actual content — not the model's general
knowledge. The interesting part isn't "call an LLM in a loop"; it's everything around that:

- **A library, not a single upload.** The app holds multiple books at once, each with its own
  conversation (chat history, reading position, answer tone), not a one-shot Q&A widget.
- **Retrieval that isn't naive fixed-size chunking.** Chunking is chapter/section-aware (using
  the PDF's own table of contents when present, falling back to heading heuristics), with overlap
  between adjacent chunks. Retrieval itself is hybrid: BM25 keyword search and vector similarity
  search run in parallel, merged with Reciprocal Rank Fusion, then re-scored by a cross-encoder
  reranker — so a query has to actually match the text well (not just embed nearby) to surface.
- **A real refusal path.** If nothing retrieved is actually relevant (a hard threshold on the
  reranker's own score, not left to LLM judgment), the app says so — in a naturally-worded,
  memory-aware refusal — instead of guessing from the model's general knowledge and passing it
  off as coming from the book.
- **Conversation memory**, not just a stateless single-turn Q&A: a short-term window of recent
  messages plus a rolling summary of everything older, so pronoun follow-ups ("what about that?",
  "why not?") resolve correctly even many turns later, and even right after a refusal.
- **The full voice loop, not just text.** Recording → Whisper transcription → the RAG pipeline
  above → TTS synthesis → playback, with the user's own recording and the spoken answer both
  saved and replayable later, not just played once and discarded.
- **Runtime-configurable, not hardcoded.** The OpenAI API key, TTS voice, and speaking speed are
  all editable from the app's own Settings page and take effect immediately (no restart, no
  `.env` hand-editing) — see [Method 1](#method-1-one-click-launcher-recommended) below for how
  little setup that actually requires.

The original brief (translated from Chinese) explicitly calls out five things it's graded on:
third-party service selection, **retrieval quality** (naive fixed-size chunking is flagged as
insufficient), creativity, engineering/AI-assisted-development practice, and UI/design taste —
the design choices above (and the [Evaluation](#evaluation) section further down) are aimed
squarely at those.

### Tech stack

| Layer | Choice |
|---|---|
| Frontend | React + TypeScript, Vite |
| Backend | FastAPI (Python) |
| Metadata/session storage | SQLite |
| PDF parsing | PyMuPDF |
| Vector store | ChromaDB |
| Keyword search | BM25 (`rank-bm25`) |
| Hybrid merge | Reciprocal Rank Fusion (BM25 + vector) |
| Reranker | Cross-encoder (`sentence-transformers`, `ms-marco-MiniLM-L-6-v2`) |
| LLM / ASR / TTS | OpenAI — `gpt-4o-mini`, Whisper (`whisper-1`), `gpt-4o-mini-tts` |
| Audio capture | Browser `MediaRecorder` API |

## Prerequisites

- **Python 3.11+** (tested on 3.13/3.14)
- **Node.js 20+** and npm (tested on Node 20)
- **An OpenAI API key** — https://platform.openai.com/api-keys. Used for embeddings, chat
  completions, Whisper transcription, and text-to-speech. You don't need this key until the
  app is already running — it's entered from the app's own **Settings** page, not by editing
  any file by hand.

Nothing else needs to be installed manually — the launcher (or the manual steps below) creates
the Python virtual environment and installs all dependencies for you.

## Method 1: One-click launcher (recommended)

**macOS:** double-click **`Start Demo.command`** in the project root. Finder will ask about
running a script the first time — click **Open**. A Terminal window opens and shows progress;
leave it open while you use the app.

**Windows:** double-click **`start.bat`** in the project root (a Command Prompt window opens
automatically and shows progress). Requires Python installed with **"Add python.exe to PATH"**
checked during setup, and Node.js installed — both installers do this by default if you don't
change anything.

**Or from a terminal** (macOS/Linux: `./start.sh`, Windows Command Prompt: `start.bat`).

The script:

1. Checks that Python and npm are installed.
2. Creates `backend/venv/` and installs Python dependencies (first run only — this step downloads
   a few hundred MB of ML libraries plus a small reranker model, so it can take a few minutes;
   later runs are fast).
3. Creates an empty `backend/.env` from `backend/.env.example` if one doesn't already exist.
4. Runs `npm install` for the frontend (first run only).
5. Starts the backend (`:8000`) and frontend (`:5173`), waits for the backend to be ready, and
   opens the app in your default browser automatically.
6. Frees up ports 8000/5173 first if a previous run is still using them, so it's safe to just
   run it again.

**macOS/Linux:** both servers run in the same terminal; press **Ctrl+C** there to stop them
cleanly, and check `logs/backend.log` / `logs/frontend.log` if something goes wrong.

**Windows:** the backend and frontend each open in their own Command Prompt window (their
output is right there, not in a log file) — close both windows, or press Ctrl+C in each, to
stop the app. The original launcher window pauses at the end with a summary; press any key
there once you're done.

### First-time setup inside the app

Once the app opens: go to **Settings** → paste your OpenAI API key → **Save key**. Until a key
is saved, uploading a PDF or asking a question shows a toast asking you to add one — nothing
will silently fail.

## Method 2: Manual setup (step by step)

If you'd rather run everything yourself, from the project root:

### 1. Backend

**macOS/Linux:**

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # creates an empty .env; the API key is added via Settings, not here
uvicorn app.main:app --reload --port 8000
```

**Windows (Command Prompt):**

```bat
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

Leave this running. The API is now live at `http://localhost:8000`.

### 2. Frontend

In a **second** terminal, from the project root:

```bash
cd frontend
npm install
npm run dev
```

Vite prints the local URL (`http://localhost:5173`) — open that in your browser.

### 3. Add your API key

In the app: **Settings** → paste your OpenAI API key → **Save key**.

### Stopping

Press **Ctrl+C** in each terminal (backend and frontend).

## Evaluation

There are three layers of checks in this project, each covering something different. All of
them need the backend's virtual environment active and a real `OPENAI_API_KEY` in `backend/.env`
(they make real OpenAI calls — no mocking anywhere in this project).

### 1. The pytest suite — correctness of every endpoint

The main automated test suite. Covers upload/ingestion, chat, voice (`/ask`), settings
(including the API-key gating and rate limits), and the RAG pipeline (query analysis, retrieval,
refusal gate, memory) — status codes, persistence, audio generation, citations, and edge cases.
Runs against an isolated temp database/vector-store/`.env` copy (see `backend/tests/conftest.py`),
so it never touches your real data.

```bash
cd backend
source venv/bin/activate        # Windows: venv\Scripts\activate
pytest -q
```

Takes a couple of minutes (real API calls). A single file can be run on its own, e.g.
`pytest tests/test_chat.py -q`.

### 2. `scripts/eval_retrieval.py` — retrieval quality in isolation

Runs a fixed set of queries (`backend/eval/queries.json`) through vector-only search and the
full hybrid pipeline (BM25 + vector RRF → cross-encoder rerank) side by side, judges each with
an LLM, and reports a hit-rate comparison. This is what actually demonstrates the retrieval
strategy is better than naive search — the brief specifically calls out retrieval quality as
the part most likely to be scrutinized. Needs the sample book already uploaded and ready (use
the app, or `--document-id` to point at a specific one).

```bash
cd backend
source venv/bin/activate        # Windows: venv\Scripts\activate
python scripts/eval_retrieval.py [--document-id ID] [--out eval/results.json]
```

### 3. `scripts/run_qa_benchmark.py` — does the full answer pipeline actually work

The other two check components in isolation; this one hits `/chat` end-to-end with a fixed set
of real questions about the sample book (`backend/scripts/qa_benchmark.json`) and checks each
answer for the facts it should contain — e.g. "What BLEU score did the model get on
English-to-German?" must mention `28.4`. One case is deliberately out-of-scope (a cookie
recipe question) and checks that the refusal gate fires instead of guessing. Each case runs in
its own fresh conversation. Prints a PASS/FAIL per case and a summary; exits non-zero if
anything failed.

```bash
cd backend
source venv/bin/activate        # Windows: venv\Scripts\activate
python scripts/run_qa_benchmark.py [--document-id ID] [--cases scripts/qa_benchmark.json]
```

Uses `fastapi.testclient.TestClient` against the app in-process (like the pytest suite), but
against your **real** dev database — so it needs the sample book (`attention_is_all_you_need`)
already ingested, either via the app's upload flow or via `pytest tests/test_documents_ingestion.py`.

## Troubleshooting

- **"Port already in use"**: another process is already bound to 8000 or 5173. The launcher
  script handles this automatically; if running manually, stop whatever's using that port or
  pass a different port to `uvicorn`/`vite`.
- **First backend request is slow**: the cross-encoder reranker model downloads from Hugging
  Face on first startup. This only happens once — it's cached afterward.
- **"Set up your OpenAI API key in Settings first"**: expected until you've saved a key on the
  Settings page — see above.
- **Uploads/answers fail with an OpenAI error**: double check the key on the Settings page is
  correct and has available quota; save it again to retry without restarting the server.
