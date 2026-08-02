import { useEffect, useRef, useState } from "react";
import { Streamdown } from "streamdown";
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
import { showToast } from "./Toast";

interface ChatAreaProps {
  t: Strings;
  documentId: string;
  documentTitle: string;
  totalPages: number | null;
  conversation: ConversationOut;
  onConversationUpdate: (patch: Partial<ConversationOut>) => void;
  isApiKeyConfigured: boolean;
}

const TONES: AnswerTone[] = ["concise", "conversational", "scholarly"];
const MIN_PDF_PANE_WIDTH = 320;
const MIN_CHAT_PANE_WIDTH = 320;
const DEFAULT_PDF_PANE_WIDTH = 520;
// container padding (space-6 * 2) + .plate border (6px * 2), added on top of the
// image's own rendered width so the pane fits the page with its usual framing.
const PANE_HORIZONTAL_OVERHEAD = 68;
const PLATE_MAX_WIDTH = 460;
const ZOOM_MIN = 0.5;
const ZOOM_MAX = 3;
const ZOOM_STEP = 0.25;

// Minimal inline icons (no matching glyphs in the existing icon set) --
// consider moving these into icons.tsx alongside the others if kept.
function ZoomOutIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="7" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
      <line x1="8" y1="11" x2="14" y2="11" />
    </svg>
  );
}
function ZoomInIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="7" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
      <line x1="11" y1="8" x2="11" y2="14" />
      <line x1="8" y1="11" x2="14" y2="11" />
    </svg>
  );
}
function FullscreenEnterIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 8V5a2 2 0 0 1 2-2h3" />
      <path d="M21 8V5a2 2 0 0 0-2-2h-3" />
      <path d="M3 16v3a2 2 0 0 0 2 2h3" />
      <path d="M21 16v3a2 2 0 0 1-2 2h-3" />
    </svg>
  );
}
function FullscreenExitIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 3v3a2 2 0 0 1-2 2H3" />
      <path d="M16 3v3a2 2 0 0 0 2 2h3" />
      <path d="M8 21v-3a2 2 0 0 0-2-2H3" />
      <path d="M16 21v-3a2 2 0 0 1 2-2h3" />
    </svg>
  );
}

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

export default function ChatArea({ t, documentId, documentTitle, totalPages, conversation, onConversationUpdate, isApiKeyConfigured }: ChatAreaProps) {
  const [chapters, setChapters] = useState<ChapterOut[]>([]);
  const [messages, setMessages] = useState<MessageOut[]>([]);
  const [currentPage, setCurrentPage] = useState(conversation.current_page ?? 1);
  const [tone, setTone] = useState<AnswerTone>(conversation.answer_tone);
  const [textInput, setTextInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isBusy, setIsBusy] = useState(false);
  const [autoplayMessageId, setAutoplayMessageId] = useState<string | null>(null);
  const [pdfPaneWidth, setPdfPaneWidth] = useState<number | string>(DEFAULT_PDF_PANE_WIDTH);
  const [isResizing, setIsResizing] = useState(false);
  const [hasManuallyResized, setHasManuallyResized] = useState(false);
  const threadRef = useRef<HTMLDivElement>(null);
  const paneContainerRef = useRef<HTMLDivElement>(null);
  const pageImageRef = useRef<HTMLImageElement>(null);
  const imageScrollRef = useRef<HTMLDivElement>(null);
  const pdfPaneRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [baseImageSize, setBaseImageSize] = useState<{ width: number; height: number } | null>(null);
  const [isPanning, setIsPanning] = useState(false);
  const panStartRef = useRef<{ x: number; y: number; scrollLeft: number; scrollTop: number } | null>(null);
  const [isPaneHovered, setIsPaneHovered] = useState(false);

  function zoomIn() {
    setZoom((z) => Math.min(ZOOM_MAX, +(z + ZOOM_STEP).toFixed(2)));
  }
  function zoomOut() {
    setZoom((z) => Math.max(ZOOM_MIN, +(z - ZOOM_STEP).toFixed(2)));
  }
  function resetZoom() {
    setZoom(1);
  }

  async function toggleFullscreen() {
    if (!pdfPaneRef.current) return;
    if (document.fullscreenElement) {
      await document.exitFullscreen();
    } else {
      await pdfPaneRef.current.requestFullscreen();
    }
  }

  useEffect(() => {
    function handleFullscreenChange() {
      setIsFullscreen(document.fullscreenElement === pdfPaneRef.current);
    }
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

  function computeLayout() {
    const img = pageImageRef.current;
    const scrollEl = imageScrollRef.current;
    if (!img || !scrollEl || !img.naturalWidth || !img.naturalHeight) return;

    const style = getComputedStyle(scrollEl);
    const verticalPadding = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
    const availableHeight = scrollEl.clientHeight - verticalPadding;
    const aspect = img.naturalWidth / img.naturalHeight;

    let height = availableHeight;
    let width = height * aspect;
    if (width > PLATE_MAX_WIDTH) {
      width = PLATE_MAX_WIDTH;
      height = width / aspect;
    }
    setBaseImageSize({ width, height });

    if (hasManuallyResized) return;
    const container = paneContainerRef.current;
    if (!container) return;
    const containerRect = container.getBoundingClientRect();
    const target = Math.max(
      MIN_PDF_PANE_WIDTH,
      Math.min(width + PANE_HORIZONTAL_OVERHEAD, containerRect.width - MIN_CHAT_PANE_WIDTH),
    );
    setPdfPaneWidth(target);
  }

  function handlePanMouseDown(e: React.MouseEvent) {
    e.preventDefault();
    const scrollEl = imageScrollRef.current;
    if (!scrollEl) return;
    panStartRef.current = { x: e.clientX, y: e.clientY, scrollLeft: scrollEl.scrollLeft, scrollTop: scrollEl.scrollTop };
    setIsPanning(true);
  }

  useEffect(() => {
    if (!isPanning) return;

    function handleMouseMove(e: MouseEvent) {
      const scrollEl = imageScrollRef.current;
      const start = panStartRef.current;
      if (!scrollEl || !start) return;
      scrollEl.scrollLeft = start.scrollLeft - (e.clientX - start.x);
      scrollEl.scrollTop = start.scrollTop - (e.clientY - start.y);
    }
    function handleMouseUp() {
      setIsPanning(false);
      panStartRef.current = null;
    }

    document.body.style.userSelect = "none";
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      document.body.style.userSelect = "";
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isPanning]);

  useEffect(() => {
    const container = paneContainerRef.current;
    if (!container) return;
    const observer = new ResizeObserver(() => {
      computeLayout();
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, [hasManuallyResized]);

  useEffect(() => {
    if (!isResizing) return;

    function handleMouseMove(e: MouseEvent) {
      const container = paneContainerRef.current;
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const proposed = e.clientX - rect.left;
      const clamped = Math.max(MIN_PDF_PANE_WIDTH, Math.min(proposed, rect.width - MIN_CHAT_PANE_WIDTH));
      setPdfPaneWidth(clamped);
    }
    function handleMouseUp() {
      setIsResizing(false);
    }

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizing]);

  useEffect(() => {
    setCurrentPage(conversation.current_page ?? 1);
    setTone(conversation.answer_tone);
    setZoom(1);
    getChapters(documentId).then(setChapters);
    getMessages(conversation.id).then(setMessages);
  }, [documentId, conversation.id]);

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: "auto" });
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

  function appendUserMessage(text: string, audioPath: string | null = null): string {
    const id = `local-${Date.now()}-u`;
    setMessages((prev) => [
      ...prev,
      { id, role: "user", text, audio_path: audioPath, audio_duration_s: null, top_rerank_score: null, is_refusal: null, created_at: new Date().toISOString(), sources: [] },
    ]);
    return id;
  }

  function updateMessage(id: string, patch: Partial<MessageOut>) {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)));
  }

  function appendAssistantMessage(assistant: { id: string; text: string; sources: SourceOut[]; audio_path?: string | null; is_refusal: boolean; top_rerank_score: number | null }) {
    setMessages((prev) => [
      ...prev,
      {
        id: assistant.id,
        role: "assistant",
        text: assistant.text,
        audio_path: assistant.audio_path ?? null,
        audio_duration_s: null,
        top_rerank_score: assistant.top_rerank_score,
        is_refusal: assistant.is_refusal,
        created_at: new Date().toISOString(),
        sources: assistant.sources,
      },
    ]);
    // Every answer now always includes audio (text or voice input alike) -- mark it as
    // the one to autoplay. Historical messages loaded via getMessages() never go through
    // this function, so reopening a conversation never replays old answers.
    setAutoplayMessageId(assistant.id);
  }

  async function handleSendText() {
    const question = textInput.trim();
    if (!question || isBusy) return;
    if (!isApiKeyConfigured) {
      showToast(t.keyRequiredToast);
      return;
    }
    setTextInput("");
    appendUserMessage(question);
    setIsBusy(true);
    try {
      const response = await sendChatMessage(conversation.id, question);
      appendAssistantMessage({
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

  async function handleRecordingStop(blob: Blob) {
    setIsRecording(false);
    // Show the recording immediately (a local object URL, no server round-trip needed
    // for this) instead of a "🎤 …" placeholder -- the transcribed text is never shown
    // for a voice-originated message, only the audio itself.
    const localAudioUrl = URL.createObjectURL(blob);
    const placeholderId = appendUserMessage("", localAudioUrl);
    setIsBusy(true);
    try {
      const response = await sendAsk(conversation.id, blob);
      updateMessage(placeholderId, { text: response.question, audio_path: response.question_audio_path });
      URL.revokeObjectURL(localAudioUrl);
      appendAssistantMessage({
        id: response.message_id,
        text: response.answer,
        sources: response.sources,
        is_refusal: response.is_refusal,
        top_rerank_score: response.top_rerank_score,
        audio_path: response.audio_path,
      });
    } catch (err) {
      console.error(err);
      // Keep the local recording playable even though transcription/generation failed.
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

      <div ref={paneContainerRef} style={{ flex: 1, display: "flex", minHeight: 0 }}>
        <div
          ref={pdfPaneRef}
          onMouseEnter={() => setIsPaneHovered(true)}
          onMouseLeave={() => setIsPaneHovered(false)}
          style={{
            width: isFullscreen ? "100%" : pdfPaneWidth,
            height: isFullscreen ? "100vh" : undefined,
            flexShrink: 0,
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
            background: "var(--color-surface)",
            position: "relative",
          }}
        >
          <div
            style={{
              position: "absolute",
              top: "var(--space-3)",
              right: "var(--space-3)",
              display: "flex",
              alignItems: "center",
              gap: 2,
              background: "var(--color-bg)",
              border: "1px solid var(--color-divider)",
              borderRadius: 6,
              padding: 2,
              zIndex: 5,
              opacity: isPaneHovered ? 1 : 0,
              pointerEvents: isPaneHovered ? "auto" : "none",
              transition: "opacity 0.15s ease",
            }}
          >
            <button type="button" className="btn btn-ghost btn-icon" style={{ width: 26, height: 26 }} aria-label="Zoom out" onClick={zoomOut} disabled={zoom <= ZOOM_MIN}>
              <ZoomOutIcon />
            </button>
            <button type="button" className="btn btn-ghost" style={{ fontFamily: "var(--font-body)", fontSize: 12, minWidth: 42, padding: "0 4px", height: 26 }} aria-label="Reset zoom" onClick={resetZoom}>
              {Math.round(zoom * 100)}%
            </button>
            <button type="button" className="btn btn-ghost btn-icon" style={{ width: 26, height: 26 }} aria-label="Zoom in" onClick={zoomIn} disabled={zoom >= ZOOM_MAX}>
              <ZoomInIcon />
            </button>
            <div style={{ width: 1, alignSelf: "stretch", background: "var(--color-divider)", margin: "0 2px" }} />
            <button
              type="button"
              className="btn btn-ghost btn-icon"
              style={{ width: 26, height: 26 }}
              aria-label={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
              onClick={toggleFullscreen}
            >
              {isFullscreen ? <FullscreenExitIcon /> : <FullscreenEnterIcon />}
            </button>
          </div>
          <div
            ref={imageScrollRef}
            className="m-scroll"
            onMouseDown={handlePanMouseDown}
            style={{ flex: 1, minHeight: 0, overflow: "auto", padding: "var(--space-6)", display: "flex", cursor: isPanning ? "grabbing" : "grab" }}
          >
            <div className="plate" style={{ margin: "auto", display: "flex", alignItems: "center", justifyContent: "center", border: "none", outline: "none" }}>
              <img
                ref={pageImageRef}
                src={pageImageUrl(documentId, currentPage)}
                alt={`Page ${currentPage}`}
                onLoad={computeLayout}
                draggable={false}
                onDragStart={(e) => e.preventDefault()}
                style={{
                  display: "block",
                  background: "var(--color-bg)",
                  width: baseImageSize ? baseImageSize.width * zoom : undefined,
                  height: baseImageSize ? baseImageSize.height * zoom : undefined,
                  maxWidth: baseImageSize ? undefined : "100%",
                  maxHeight: baseImageSize ? undefined : "100%",
                  transition: "width 0.15s ease, height 0.15s ease",
                }}
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

        <div
          onMouseDown={() => {
            setIsResizing(true);
            setHasManuallyResized(true);
          }}
          style={{
            width: 8,
            flexShrink: 0,
            cursor: "col-resize",
            background: "transparent",
          }}
        />

        <div style={{ flex: 1, minWidth: MIN_CHAT_PANE_WIDTH, display: "flex", flexDirection: "column", minHeight: 0 }}>
          <div ref={threadRef} className="m-scroll" style={{ flex: 1, overflow: "auto", padding: "var(--space-6)", display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            {messages.map((msg) => {
              const isUser = msg.role === "user";
              const sources = dedupeSources(msg.sources);
              return (
                <div key={msg.id} style={{ display: "flex", flexDirection: "column", alignItems: isUser ? "flex-end" : "flex-start" }}>
                  <div
                    className="card bubble-pop"
                    style={{
                      maxWidth: "88%",
                      padding: "var(--space-2) var(--space-3)",
                      background: isUser ? "var(--color-surface)" : "var(--color-bg)",
                      borderColor: isUser ? "var(--color-neutral-300)" : "var(--color-divider)",
                      borderRadius: 6,
                    }}
                  >
                    {isUser && msg.audio_path ? (
                      // Voice-originated user message: only the recording is shown, never
                      // the transcribed text.
                      <AudioPlayer src={msg.audio_path} />
                    ) : (
                      <>
                        <div style={{ textAlign: "left", lineHeight: 1.55 }}>
                          <Streamdown>{msg.text}</Streamdown>
                        </div>
                        {sources.length > 0 && (
                          <div style={{ marginTop: "var(--space-3)", display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
                            {sources.map((s) =>
                              s.start_page != null ? (
                                <button
                                  key={sourceKey(s)}
                                  type="button"
                                  className="tag tag-outline tag-clickable"
                                  style={{ border: "1px solid var(--color-accent)" }}
                                  onClick={() => goToPage(s.start_page!)}
                                >
                                  {citationLabel(s)}
                                </button>
                              ) : (
                                <span key={sourceKey(s)} className="tag tag-outline">
                                  {citationLabel(s)}
                                </span>
                              ),
                            )}
                          </div>
                        )}
                        {msg.audio_path && (
                          <AudioPlayer
                            src={msg.audio_path}
                            autoPlay={msg.role === "assistant" && msg.id === autoplayMessageId}
                          />
                        )}
                      </>
                    )}
                  </div>
                </div>
              );
            })}
            {isBusy && (
              <div style={{ display: "flex", justifyContent: "flex-start", padding: "0 var(--space-2)" }}>
                <p className="shimmer-text" style={{ margin: 0, fontSize: 14 }}>Thinking…</p>
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
                <MicButton
                  isRecording={isRecording}
                  onStart={() => setIsRecording(true)}
                  onStop={handleRecordingStop}
                  disabled={isBusy && !isRecording}
                  onBeforeStart={() => {
                    if (!isApiKeyConfigured) {
                      showToast(t.keyRequiredToast);
                      return false;
                    }
                    return true;
                  }}
                />
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