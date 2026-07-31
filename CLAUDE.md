# Take Home Demo — Voice PDF Book Q&A

## Coding guidelines

Behavioral guidelines to reduce common LLM coding mistakes. These apply on top of the
project-specific content below, for all coding work in this repo. Bias toward caution over speed;
for trivial tasks, use judgment.

### 1. Think before coding

Don't assume. Don't hide confusion. Surface tradeoffs.

- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity first

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical changes

Touch only what you must. Clean up only your own mess.

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: every changed line should trace directly to the user's request.

### 4. Goal-driven execution

Define success criteria. Loop until verified.

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria allow independent looping. Weak criteria ("make it work") require constant
clarification.

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to
overcomplication, and clarifying questions come before implementation rather than after mistakes.

## Objective

A web app where a user uploads a PDF book (≥10 chapters, size otherwise unrestricted) and has a
**spoken conversation** with it: ask a question by voice, get a spoken answer back, grounded in
that book's actual content.

Source requirement doc: `Take Home 作业.docx` (Chinese). Translated core flow:

```
Mic input → ASR → RAG (retrieve from the book + LLM generates answer) → TTS → audio playback
```

### What the brief explicitly evaluates

This is a graded take-home; the requirements doc calls out these as the actual grading axes —
keep them in mind for every decision, not just the initial architecture:

1. **Third-party service selection** — free-trial cloud APIs are fine, no need to host models.
2. **Retrieval quality** (research ability) — naive fixed-size chunking is explicitly flagged as
   insufficient; a real retrieval-optimization strategy is required and is the part most likely to
   be scrutinized.
3. **Creativity** — value-add features beyond the core pipeline are encouraged.
4. **AI-assisted development practice** (engineering judgment) — disciplined workflow, consistent
   code standards, real acceptance criteria (unit/integration/e2e/eval), critical thinking when
   using AI tools rather than accepting output uncritically, efficient prompting.
5. **UI/design taste** — must not look like a generic "AI template"; care in layout, color,
   interaction detail is explicitly requested.

## Scope decisions (locked in during design discussion)

- **Multi-PDF**: the app supports a library of uploaded books. Each PDF maps to exactly one
  conversation (simple chat layout, not a cross-book search).
- **Language**: English-only for v1 — PDFs, ASR, TTS, and retrieval all assume English text. A UI
  language toggle (English/中文) exists but is **label-only i18n** (menus/buttons); it does not
  change ASR/TTS/RAG language capability.
- **API keys**: server-side `.env` OpenAI key. No client-supplied/BYO key flow, despite an earlier
  mockup implying otherwise.
- **current_page** (reading position) is **display-only** — it drives the UI header, but does
  **not** gate retrieval. Retrieval always searches the whole book (no spoiler-avoidance filtering).
- **Audio persistence**: each assistant answer's synthesized TTS audio is saved to disk and
  referenced from its `messages` row, so past answers remain replayable/scrubbable, not just
  played once during generation.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | React |
| Backend | FastAPI (Python) |
| Metadata/session DB | SQLite3 |
| PDF parsing | PyMuPDF |
| Chunking | Custom structure-aware chunker (chapter/section-aware, overlapping adjacent chunks) |
| Embeddings | OpenAI `text-embedding-3-small` |
| Vector DB | ChromaDB |
| Keyword search | BM25 |
| Hybrid merge | Reciprocal Rank Fusion (RRF) — requires BM25 and Chroma to key results by the **same chunk id** |
| Reranker | Cross-encoder via sentence-transformers, `ms-marco-MiniLM-L-6-v2` |
| LLM | OpenAI Chat Completions API (plain `openai` SDK), `gpt-4o-mini` for condensation/answer-gen/summary |
| ASR | OpenAI Whisper API, `whisper-1` |
| TTS | OpenAI TTS API, `gpt-4o-mini-tts` |
| Audio capture | Browser `MediaRecorder` API |

## Ingestion flow

1. Validate PDF + size limit; create `documents` row with `status='processing'`; return
   immediately — parsing runs in a background task.
2. Parse PDF (PyMuPDF) → extract text per chapter/page (prefer embedded TOC/outline via
   `get_toc()`; fall back to heading heuristics — e.g. font size/weight — when no TOC exists).
3. Chunk text: structure-aware (chapter/section boundaries), with overlap between adjacent chunks.
4. Embed each chunk (OpenAI Embeddings API).
5. Write chunk text + embedding + metadata (doc id, chapter, page) to ChromaDB.
6. Write document/chapter/chunk records to SQLite; set `status='ready'` (or `'failed'` +
   `error_message` on error).

## Query flow

**Implementation status**: `POST /conversations` creates a conversation for a document.
`POST /chat` (`{conversation_id, question}` → answer + citations) is the **text-only** path — plain
text in/out, messages saved without `audio_path`. `POST /ask` (`conversation_id` + audio file,
multipart) is the **voice** path covering steps 1-8 end-to-end: audio in → `POST /transcribe`'s
Whisper call → steps 3-8 (memory, condensation, hybrid retrieval, rerank, refusal gate, answer
generation) → `core/tts.synthesize_speech()` → saved `.mp3` → `{question, answer, is_refusal,
sources, audio_path}`, with the assistant message's `audio_path` persisted. `POST /transcribe`
(audio in, text out) also still exists standalone, used internally by `/ask` and directly testable
on its own. Step 11's background summary-update is wired for both `/chat` and `/ask`. **Not yet
implemented**: step 9's sentence-level streaming — `/ask` currently generates the full answer, then
synthesizes the full audio, then returns both together; no progressive/streamed playback yet.

1. Browser records audio (MediaRecorder) → uploads to FastAPI.
2. FastAPI calls Whisper API → transcribed text.
3. Backend pulls conversation memory for this `conversation_id` (see Memory below).
4. **Query condensation**: question + memory → LLM → standalone, context-resolved search query.
   Skipped on a conversation's first turn (no history to resolve against — free latency win).
5. **Hybrid retrieval** on the condensed query, scoped to this document only:
   - BM25 keyword search over this document's chunks.
   - Vector similarity search in ChromaDB (same document scope).
   - Merge both ranked lists with RRF (joined by shared chunk id).
6. **Rerank** merged top-k with the cross-encoder → top 3–5 chunks.
7. **Refusal gate**: if the top rerank score is below a set threshold, skip generation and return
   a canned clarifying/refusal response (hard deterministic threshold, not left to LLM judgment —
   chosen for a reliable, testable refusal case). Threshold is currently `-8.0`, a provisional value
   from one small eval run (an out-of-scope question scored -10.75 vs. -6.23..9.44 for genuinely
   answerable ones) — revisit as more real queries are observed.
8. Otherwise: original question + retrieved chunks + conversation memory + `answer_tone` → LLM
   (Chat Completions, streamed) → grounded answer.
9. **Streaming**: LLM tokens are split into sentences as they stream; each completed sentence is
   sent to TTS and the resulting audio is streamed to the frontend progressively (not
   wait-for-full-answer-then-synthesize) — chosen to reduce dead-air before the user hears
   anything.
10. Persist the answer's full audio (`/data/audio/{message_id}.mp3`) and set
    `messages.audio_path` / `audio_duration_s`.
11. Log the turn (question, answer, sources, `top_rerank_score`, `is_refusal`) to SQLite; update
    `conversations.summary` **as a background task** (must not block the response) if the memory
    window rolled over.

## Memory design

Two layers only — a semantic/vector memory tier was considered and deliberately dropped as
unnecessary complexity at single-document, single-session scale:

- **Short-term**: last N raw *messages* from `messages` (N=8, i.e. ~4 Q&A pairs), included directly
  in the prompt. Handles pronoun resolution and immediate follow-ups.
- **Long-term**: a rolling summary in `conversations.summary`. When messages fall out of the
  N-message window, they're folded into the running summary (one LLM call, run as a background
  task so it never blocks the user-facing response). `conversations.summarized_message_count`
  tracks how many of the earliest messages have already been folded in, so each update only
  summarizes the newly-fallen-out messages instead of re-summarizing the whole history every turn.
  Message rows themselves are never deleted — the full transcript still needs to render in the UI.

Both layers feed **two** places: query condensation (step 4 above) and answer generation (step 8).

## Database schema

```sql
-- One row per uploaded book
CREATE TABLE documents (
    id            TEXT PRIMARY KEY,      -- uuid
    title         TEXT NOT NULL,
    total_pages   INTEGER,
    status        TEXT NOT NULL,         -- 'processing' | 'ready' | 'failed'
    error_message TEXT,                  -- populated when status='failed'
    file_path     TEXT,                  -- original PDF on disk, e.g. /data/documents/{id}.pdf
    uploaded_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chapter boundaries, needed for citations and chapter jump/nav
CREATE TABLE chapters (
    id              TEXT PRIMARY KEY,
    document_id     TEXT NOT NULL REFERENCES documents(id),
    chapter_number  INTEGER NOT NULL,
    title           TEXT,
    start_page      INTEGER,
    end_page        INTEGER
);

-- Chunk text — source of truth for BM25 index; Chroma holds a copy + embedding,
-- keyed by the SAME id so RRF can merge the two ranked lists by identity.
CREATE TABLE chunks (
    id            TEXT PRIMARY KEY,
    document_id   TEXT NOT NULL REFERENCES documents(id),
    chapter_id    TEXT REFERENCES chapters(id),
    chunk_index   INTEGER NOT NULL,
    text          TEXT NOT NULL,
    start_page    INTEGER,
    end_page      INTEGER
);

-- One row per conversation — always bound to a single book
CREATE TABLE conversations (
    id            TEXT PRIMARY KEY,
    document_id   TEXT NOT NULL REFERENCES documents(id),
    title         TEXT,                  -- defaults to document title, editable
    answer_tone   TEXT DEFAULT 'conversational',  -- 'concise' | 'conversational' | 'scholarly'
    current_page  INTEGER,               -- drives the reading-position header ONLY (display, not retrieval gating)
    summary       TEXT,                  -- rolling long-term memory summary
    summarized_message_count INTEGER DEFAULT 0,  -- how many earliest messages are already folded into summary
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- One row per turn (both user question and assistant answer)
CREATE TABLE messages (
    id                TEXT PRIMARY KEY,
    conversation_id   TEXT NOT NULL REFERENCES conversations(id),
    role              TEXT NOT NULL,     -- 'user' | 'assistant'
    text              TEXT NOT NULL,
    audio_path        TEXT,              -- file path/URL; null for text-only turns
    audio_duration_s  REAL,              -- drives the displayed audio duration
    top_rerank_score  REAL,              -- assistant rows only; the retrieval confidence signal
    is_refusal        BOOLEAN,           -- assistant rows only; set when the refusal gate fired
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Citations shown under an answer — separate table since an answer can cite >1 range
CREATE TABLE message_sources (
    id            TEXT PRIMARY KEY,
    message_id    TEXT NOT NULL REFERENCES messages(id),
    chapter_id    TEXT REFERENCES chapters(id),
    start_page    INTEGER,
    end_page      INTEGER,
    chunk_id      TEXT REFERENCES chunks(id)   -- optional, for debugging/traceability
);
```

Design notes:
- `chunks.text` is duplicated into Chroma — Chroma needs raw text alongside the embedding to
  return it on search; SQLite needs it as the BM25 corpus. Each store must function independently.
- Audio and original PDFs are stored as files on disk (`/data/audio/{message_id}.mp3`,
  `/data/documents/{document_id}.pdf`), with only the path kept in SQLite.
- BM25 retrieval must be scoped to a single document's chunks (`WHERE document_id = ?`) — it is
  never a cross-book search.
- `message_sources` is its own table (not columns on `messages`) so an answer can cite multiple
  non-contiguous page ranges without a schema change later.

## Folder structure

```
project-root/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app entrypoint, mounts routes + static frontend
│   │   ├── config.py                # pydantic-settings, reads .env
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── documents.py     # upload PDF, list documents/chapters
│   │   │       └── chat.py          # POST audio -> ASR -> RAG -> TTS -> audio response
│   │   ├── core/
│   │   │   ├── pdf_parser.py        # PyMuPDF extraction
│   │   │   ├── chunker.py           # structure-aware chunking
│   │   │   ├── embeddings.py        # OpenAI embeddings client
│   │   │   ├── vector_store.py      # ChromaDB client wrapper
│   │   │   ├── keyword_search.py    # BM25 index + search
│   │   │   ├── retrieval.py         # RRF merge of BM25 + vector results
│   │   │   ├── reranker.py          # cross-encoder reranking
│   │   │   ├── rag.py               # orchestrates memory -> query condensation -> retrieval -> LLM call
│   │   │   ├── memory.py            # short-term window + rolling summary helper
│   │   │   ├── asr.py               # Whisper API client
│   │   │   └── tts.py               # OpenAI TTS API client
│   │   ├── db/
│   │   │   ├── models.py            # SQLAlchemy models (Document, Chapter, Chunk, Conversation, Message, MessageSource)
│   │   │   └── session.py           # SQLite engine/session setup
│   │   └── schemas/
│   │       ├── document.py          # Pydantic request/response models
│   │       └── chat.py
│   ├── static/                      # built React app copied here for deployment
│   ├── data/
│   │   ├── app.db                   # SQLite file
│   │   └── chroma/                  # ChromaDB persistence directory
│   ├── tests/
│   │   ├── fixtures/                # sample PDFs used across tests (e.g. attention_is_all_you_need.pdf)
│   │   ├── test_documents_ingestion.py
│   │   ├── test_retrieval.py
│   │   ├── test_chat.py
│   │   └── ...                      # one test file per module/endpoint being covered
│   ├── scripts/
│   │   ├── qa_benchmark.json        # QA benchmark cases (phase 13 evaluation)
│   │   └── run_qa_benchmark.py      # runner: hits /chat, checks keyword coverage, reports pass/fail
│   ├── requirements.txt
│   ├── .env                         # actual secrets, gitignored
│   └── .env.example                 # committed template, no real values
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── PdfUpload.tsx
│   │   │   ├── ChatArea.tsx
│   │   │   ├── MicButton.tsx
│   │   │   └── AudioPlayer.tsx
│   │   ├── pages/
│   │   │   └── Home.tsx
│   │   ├── api/
│   │   │   └── client.ts            # fetch wrappers for backend endpoints
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts               # dev-time proxy to FastAPI on :8000
│
├── .gitignore                       # backend/data/, backend/.env, node_modules/, venv/, __pycache__/
└── README.md                        # setup, run instructions, design notes
```

## Frontend design reference

A visual/structural mockup exists in the Claude Design project **"Take Home Demo"**
(`projectId: 58686eb4-9ad9-40dc-9580-5edda13b935f`, file `Take Home Demo.dc.html`), fetched via the
`DesignSync` tool. Treat it as a structural/visual spec, **not** literal source to copy — it uses
Claude Design's own proprietary preview runtime (`<x-dc>`, `sc-if`, `sc-for` custom tags,
`image-slot.js`, `support.js`) which has no equivalent in a real React app; the actual behavior
must be reimplemented in React.

Key structural/visual points to preserve:
- Aesthetic: warm parchment background (`#FAF5F0`), deep burgundy accent (`#7A2333`), serif/humanist
  type pairing, dark navy collapsible sidebar — deliberately not a generic AI-template look.
- Sidebar: app name, "New book" / "Library" / "Settings" nav, and a per-book conversation list
  (each entry deletable).
- Library view: grid of book cards (cover, title, author, page-count tag, progress tag), search
  bar, "Upload PDF" button.
- Chat view: header shows the open book + current chapter, plus an **"Answer tone" selector**
  (Concise / Conversational / Scholarly) driving `conversations.answer_tone`. Split panel: left
  side shows the actual PDF page (rendered image, or styled text excerpt when available, with
  prev/next page nav); right side is the chat thread. Assistant messages show a citation tag
  (e.g. "Section 3.2.2, p. 4") and a scrubbable audio player (play/pause, progress bar, duration).
- Upload dialog: drag-and-drop PDF, "PDF only · up to 200 pages" hint.
- Settings view: language toggle only (English/中文, label-only per the scope decision above) —
  the mockup's API-key field is **not** part of the actual implementation (server-side `.env` key
  instead, see Scope decisions).

## Working agreement

- This file should stay current as decisions evolve — update it when scope or architecture
  changes, don't let it drift from what's actually being built.
- Discuss before implementing anything non-trivial; don't jump straight to code on ambiguous asks.
