import { useState } from "react";
import type { DocumentListItem } from "../api/client";
import type { Strings } from "../i18n";
import { LibraryIcon, PanelIcon, PlusIcon, SettingsIcon, TrashIcon } from "./icons";

type View = "library" | "settings" | "chat";

interface SidebarProps {
  t: Strings;
  open: boolean; // "pinned" -- stays expanded regardless of hover
  onToggle: () => void; // toggles pinned state
  view: View;
  documents: DocumentListItem[];
  selectedDocumentId: string | null;
  onNewBook: () => void;
  onShowLibrary: () => void;
  onShowSettings: () => void;
  onOpenBook: (documentId: string) => void;
  onDeleteConversation: (documentId: string, conversationId: string) => void;
}

const SIDEBAR_WIDTH_OPEN = 288;
const SIDEBAR_WIDTH_CLOSED = 56;

function sessionMeta(t: Strings, doc: DocumentListItem): string {
  if (!doc.current_page) return t.notStarted;
  return doc.total_pages ? t.pageOf(doc.current_page, doc.total_pages) : t.pageOf(doc.current_page, doc.current_page);
}

export default function Sidebar({
  t,
  open: pinned,
  onToggle: onTogglePin,
  view,
  documents,
  selectedDocumentId,
  onNewBook,
  onShowLibrary,
  onShowSettings,
  onOpenBook,
  onDeleteConversation,
}: SidebarProps) {
  const [isHovering, setIsHovering] = useState(false);
  const sessions = documents.filter((d) => d.conversation_id);
  const expanded = pinned || isHovering;

  return (
    <div
      className="m-sidebar"
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
      style={{
        width: expanded ? SIDEBAR_WIDTH_OPEN : SIDEBAR_WIDTH_CLOSED,
        transition: "width 0.2s ease",
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        overflow: "hidden",
      }}
    >
      {expanded ? (
        <div style={{ display: "flex", flexDirection: "column", padding: "var(--space-6) var(--space-4)", gap: "var(--space-6)", height: "100%", minWidth: SIDEBAR_WIDTH_OPEN }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "var(--space-2)" }}>
            <div style={{ fontFamily: "var(--font-heading)", fontWeight: "var(--font-heading-weight)" as unknown as number, fontSize: 23, padding: "0 var(--space-1)", whiteSpace: "nowrap" }}>
              {t.appName}
            </div>
            <button
              type="button"
              className="btn btn-ghost btn-icon"
              aria-label={pinned ? "Unpin sidebar" : "Pin sidebar open"}
              aria-pressed={pinned}
              onClick={onTogglePin}
              style={{ background: pinned ? "rgba(255, 255, 255, 0.1)" : undefined }}
            >
              <PanelIcon />
            </button>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
            <button type="button" className="m-navlink" onClick={onNewBook}>
              <span className="m-newchat-badge">
                <PlusIcon size={12} />
              </span>
              {t.newBook}
            </button>
            <button type="button" className={`m-navlink ${view === "library" ? "active" : ""}`} onClick={onShowLibrary}>
              <LibraryIcon />
              {t.library}
            </button>
            <button type="button" className={`m-navlink ${view === "settings" ? "active" : ""}`} onClick={onShowSettings}>
              <SettingsIcon />
              {t.settingsNav}
            </button>
          </div>

          <div className="hr-dark" style={{ margin: 0, paddingTop: "var(--space-4)", flex: 1, display: "flex", flexDirection: "column", minHeight: 0, gap: "var(--space-3)" }}>
            <div style={{ fontSize: 11, letterSpacing: "0.08em", textTransform: "uppercase", opacity: 0.5, padding: "0 var(--space-1)" }}>
              {t.conversations}
            </div>
            <div className="m-scroll" style={{ flex: 1, overflow: "auto", display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
              {sessions.map((doc) => (
                <div key={doc.id} className={`m-session ${view === "chat" && selectedDocumentId === doc.id ? "active" : ""}`}>
                  <div style={{ flex: 1, minWidth: 0, cursor: "pointer" }} onClick={() => onOpenBook(doc.id)}>
                    <div style={{ fontSize: 14, fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {doc.title}
                    </div>
                    <div style={{ fontSize: 12, opacity: 0.55, marginTop: 2 }}>{sessionMeta(t, doc)}</div>
                  </div>
                  <button
                    type="button"
                    className="m-session-delete"
                    aria-label="Delete conversation"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (doc.conversation_id) onDeleteConversation(doc.id, doc.conversation_id);
                    }}
                  >
                    <TrashIcon />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "var(--space-6) 0", gap: "var(--space-4)", minWidth: SIDEBAR_WIDTH_CLOSED }}>
          <button
            type="button"
            className="btn btn-ghost btn-icon"
            aria-label="Pin sidebar open"
            aria-pressed={pinned}
            onClick={onTogglePin}
            style={{ background: pinned ? "rgba(255, 255, 255, 0.1)" : undefined }}
          >
            <PanelIcon />
          </button>
          <div className="hr-dark" style={{ width: 24 }} />
          <button type="button" className="btn btn-ghost btn-icon" aria-label={t.newBook} onClick={onNewBook}>
            <PlusIcon size={16} />
          </button>
          <button type="button" className="btn btn-ghost btn-icon" aria-label={t.library} onClick={onShowLibrary}>
            <LibraryIcon />
          </button>
          <button type="button" className="btn btn-ghost btn-icon" aria-label={t.settingsNav} onClick={onShowSettings}>
            <SettingsIcon />
          </button>
        </div>
      )}
    </div>
  );
}