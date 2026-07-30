import { useEffect, useRef, useState } from "react";
import {
  getChapters,
  getMessages,
  pageImageUrl,
  sendAsk,
  sendChatMessage,
  updateConversation,
  type AnswerTone,
  type ChapterOut,
  type ConversationOut,
  type MessageOut,
  type SourceOut,
} from "../api/client";
import type { Strings } from "../i18n";
import AudioPlayer from "./AudioPlayer";
import { ChevronLeftIcon, ChevronRightIcon, SendIcon } from "./icons";
import MicButton from "./MicButton";

interface ChatAreaProps {
  t: Strings;
  documentId: string;
  documentTitle: string;
  totalPages: number | null;
  conversation: ConversationOut;
  onConversationUpdate: (patch: Partial<ConversationOut>) => void;
}

const TONES: AnswerTone[] = ["concise", "conversational", "scholarly"];

function sourceKey(s: SourceOut): string {
  return `${s.chapter_title ?? "?"}|${s.start_page ?? "?"}-${s.end_page ?? "?"}`;
}

function dedupeSources(sources: SourceOut[]): SourceOut[] {
  const seen = new Set<string>();
  return sources.filter((s) => {
    const key = sourceKey(s);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function citationLabel(s: SourceOut): string {
  if (s.chapter_title && s.start_page != null) {
    return s.end_page && s.end_page !== s.start_page
      ? `${s.chapter_title}, p. ${s.start_page}-${s.end_page}`
      : `${s.chapter_title}, p. ${s.start_page}`;
  }
  return s.chapter_title ?? "Source";
}

export default function ChatArea({ t, documentId, documentTitle, totalPages, conversation, onConversationUpdate }: ChatAreaProps) {
  const [chapters, setChapters] = useState<ChapterOut[]>([]);
  const [messages, setMessages] = useState<MessageOut[]>([]);
  const [currentPage, setCurrentPage] = useState(conversation.current_page ?? 1);
  const [tone, setTone] = useState<AnswerTone>(conversation.answer_tone);
  const [textInput, setTextInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isBusy, setIsBusy] = useState(false);
  const threadRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setCurrentPage(conversation.current_page ?? 1);
    setTone(conversation.answer_tone);
    getChapters(documentId).then(setChapters);
    getMessages(conversation.id).then(setMessages);
  }, [documentId, conversation.id]);

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const currentChapter = chapters.find((c) => c.start_page != null && c.end_page != null && currentPage >= c.start_page! && currentPage <= c.end_page!);

  function goToPage(page: number) {
    const clamped = Math.max(1, Math.min(totalPages ?? page, page));
    setCurrentPage(clamped);
    updateConversation(conversation.id, { current_page: clamped }).catch(() => {});
    onConversationUpdate({ current_page: clamped });
  }

  function handleToneChange(newTone: AnswerTone) {
    setTone(newTone);
    updateConversation(conversation.id, { answer_tone: newTone }).catch(() => {});
    onConversationUpdate({ answer_tone: newTone });
  }

  function appendTurn(userText: string, assistant: { id: string; text: string; sources: SourceOut[]; audio_path?: string | null; is_refusal: boolean; top_rerank_score: number | null }) {
    const now = new Date().toISOString();
    setMessages((prev) => [
      ...prev,
      { id: `local-${now}-u`, role: "user", text: userText, audio_path: null, audio_duration_s: null, top_rerank_score: null, is_refusal: null, created_at: now, sources: [] },
      {
        id: assistant.id,
        role: "assistant",
        text: assistant.text,
        audio_path: assistant.audio_path ?? null,
        audio_duration_s: null,
        top_rerank_score: assistant.top_rerank_score,
        is_refusal: assistant.is_refusal,
        created_at: now,
        sources: assistant.sources,
      },
    ]);
  }

  async function handleSendText() {
    const question = textInput.trim();
    if (!question || isBusy) return;
    setTextInput("");
    setIsBusy(true);
    try {
      const response = await sendChatMessage(conversation.id, question);
      appendTurn(question, { id: response.message_id, text: response.answer, sources: response.sources, is_refusal: response.is_refusal, top_rerank_score: response.top_rerank_score });
    } catch (err) {
      console.error(err);
    } finally {
      setIsBusy(false);
    }
  }

  async function handleRecordingStop(blob: Blob) {
    setIsRecording(false);
    setIsBusy(true);
    try {
      const response = await sendAsk(conversation.id, blob);
      appendTurn(response.question, {
        id: response.message_id,
        text: response.answer,
        sources: response.sources,
        is_refusal: response.is_refusal,
        top_rerank_score: response.top_rerank_score,
        audio_path: response.audio_path,
      });
    } catch (err) {
      console.error(err);
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)", padding: "var(--space-4) var(--space-6)", borderBottom: "1px solid var(--color-divider)", flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 160 }}>
          <div style={{ fontFamily: "var(--font-heading)", fontWeight: "var(--font-heading-weight)" as unknown as number, fontSize: 21 }}>
            {documentTitle}
          </div>
          <div style={{ opacity: 0.6, fontSize: 13 }}>{currentChapter?.title ?? ""}</div>
        </div>
        <div className="field" style={{ margin: 0 }}>
          <label id="tone-label" style={{ fontSize: 11, letterSpacing: "0.08em", textTransform: "uppercase", opacity: 0.55 }}>
            {t.answerTone}
          </label>
          <div className="seg" role="radiogroup" aria-labelledby="tone-label">
            {TONES.map((toneOption) => (
              <label className="seg-opt" key={toneOption}>
                <input type="radio" name="tone" checked={tone === toneOption} onChange={() => handleToneChange(toneOption)} />
                {toneOption === "concise" ? t.toneConcise : toneOption === "conversational" ? t.toneConversational : t.toneScholarly}
              </label>
            ))}
          </div>
        </div>
      </div>

      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(320px,0.9fr)", minHeight: 0 }}>
        <div style={{ borderRight: "1px solid var(--color-divider)", display: "flex", flexDirection: "column", minHeight: 0, background: "var(--color-surface)" }}>
          <div className="m-scroll" style={{ flex: 1, overflow: "auto", padding: "var(--space-6)", display: "flex", justifyContent: "center" }}>
            <div className="plate" style={{ width: "100%", maxWidth: 460 }}>
              <img
                src={pageImageUrl(documentId, currentPage)}
                alt={`Page ${currentPage}`}
                style={{ width: "100%", display: "block", background: "var(--color-bg)" }}
              />
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "var(--space-4)", padding: "var(--space-3)", borderTop: "1px solid var(--color-divider)" }}>
            <button type="button" className="btn btn-ghost btn-icon" aria-label="Previous page" onClick={() => goToPage(currentPage - 1)} disabled={currentPage <= 1}>
              <ChevronLeftIcon />
            </button>
            <span style={{ fontSize: 13, opacity: 0.65 }}>{totalPages ? t.pageOf(currentPage, totalPages) : `Page ${currentPage}`}</span>
            <button type="button" className="btn btn-ghost btn-icon" aria-label="Next page" onClick={() => goToPage(currentPage + 1)} disabled={!!totalPages && currentPage >= totalPages}>
              <ChevronRightIcon />
            </button>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
          <div ref={threadRef} className="m-scroll" style={{ flex: 1, overflow: "auto", padding: "var(--space-6)", display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            {messages.map((msg) => {
              const isUser = msg.role === "user";
              const sources = dedupeSources(msg.sources);
              return (
                <div key={msg.id} style={{ display: "flex", flexDirection: "column", alignItems: isUser ? "flex-end" : "flex-start" }}>
                  <div
                    className="card"
                    style={{
                      maxWidth: "88%",
                      padding: "var(--space-4)",
                      background: isUser ? "var(--color-surface)" : "var(--color-bg)",
                      borderColor: isUser ? "var(--color-neutral-300)" : "var(--color-divider)",
                      borderRadius: 6,
                    }}
                  >
                    <p style={{ margin: 0, textAlign: "left", lineHeight: 1.55 }}>{msg.text}</p>
                    {sources.length > 0 && (
                      <div style={{ marginTop: "var(--space-3)", display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
                        {sources.map((s) => (
                          <span key={sourceKey(s)} className="tag tag-outline">
                            {citationLabel(s)}
                          </span>
                        ))}
                      </div>
                    )}
                    {msg.role === "assistant" && msg.audio_path && <AudioPlayer src={msg.audio_path} />}
                  </div>
                </div>
              );
            })}
            {isBusy && (
              <div style={{ display: "flex", justifyContent: "flex-start" }}>
                <div className="card" style={{ padding: "var(--space-4)", borderRadius: 6, opacity: 0.6 }}>
                  <p style={{ margin: 0 }}>…</p>
                </div>
              </div>
            )}
          </div>

          <div style={{ padding: "var(--space-3) var(--space-6) var(--space-4)" }}>
            <div style={{ border: "1px solid var(--color-divider)", borderRadius: 6, padding: "var(--space-3) var(--space-2) var(--space-2) var(--space-3)", display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
              {isRecording ? (
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", minHeight: 22, color: "var(--color-accent)", fontSize: 14 }}>
                  <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--color-accent)", flexShrink: 0 }} />
                  {t.listening}
                </div>
              ) : (
                <textarea
                  rows={1}
                  placeholder={t.composerPlaceholder}
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSendText();
                    }
                  }}
                  disabled={isBusy}
                  style={{ border: "none", outline: "none", background: "transparent", resize: "none", fontFamily: "var(--font-body)", fontSize: 14, lineHeight: 1.5, color: "var(--color-text)", width: "100%", minHeight: 22, maxHeight: 120, padding: 0 }}
                />
              )}
              <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: "var(--space-1)" }}>
                <MicButton isRecording={isRecording} onStart={() => setIsRecording(true)} onStop={handleRecordingStop} disabled={isBusy && !isRecording} />
                <button type="button" className="btn btn-ghost btn-icon" style={{ width: 32, height: 32, color: "var(--color-accent)" }} aria-label="Send" onClick={handleSendText} disabled={isBusy || !textInput.trim()}>
                  <SendIcon />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
