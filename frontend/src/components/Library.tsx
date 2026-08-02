import { useMemo, useState } from "react";
import type { DocumentListItem } from "../api/client";
import type { Strings } from "../i18n";
import { TrashIcon } from "./icons";

interface LibraryProps {
  t: Strings;
  documents: DocumentListItem[];
  onOpenBook: (documentId: string) => void;
  onUploadClick: () => void;
  onDeleteDocument: (documentId: string) => void;
}

// Deterministic accent-tinted placeholder cover (no real cover art available),
// so cards still read as distinct books rather than identical stock icons.
const COVER_TINTS = ["#7A2333", "#8A6D5C", "#4A392E", "#5E1A27", "#6B5346"];

function coverTint(title: string): string {
  let hash = 0;
  for (const char of title) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return COVER_TINTS[hash % COVER_TINTS.length];
}

export default function Library({ t, documents, onOpenBook, onUploadClick, onDeleteDocument }: LibraryProps) {
  const [query, setQuery] = useState("");
  const [isSearchFocused, setIsSearchFocused] = useState(false);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return documents;
    return documents.filter(
      (d) => d.title.toLowerCase().includes(q) || (d.author ?? "").toLowerCase().includes(q),
    );
  }, [documents, query]);

  return (
    <div className="m-scroll" style={{ flex: 1, overflow: "auto", padding: "var(--space-8) var(--space-6)" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-end",
          gap: "var(--space-4)",
          flexWrap: "wrap",
          marginBottom: "var(--space-6)",
          maxWidth: 1100,
          marginLeft: "auto",
          marginRight: "auto",
        }}
      >
        <div>
          <h1 style={{ fontSize: 40, margin: 0 }}>{t.libraryTitle}</h1>
          <p style={{ opacity: 0.65, margin: "var(--space-2) 0 0", maxWidth: "52ch" }}>{t.librarySubtitle}</p>
        </div>
        <div style={{ display: "flex", gap: "var(--space-3)", alignItems: "center" }}>
          <div style={{ position: "relative" }}>
            <svg
              style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", pointerEvents: "none", color: isSearchFocused ? "var(--color-neutral-600)" : "var(--color-neutral-500)", transition: "color 0.2s ease" }}
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              className="input"
              placeholder={t.searchPlaceholder}
              style={{
                width: isSearchFocused ? 300 : 240,
                paddingLeft: 32,
                borderColor: isSearchFocused ? "var(--color-neutral-600)" : "var(--color-divider)",
                transition: "border-color 0.2s ease, width 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
              }}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => setIsSearchFocused(true)}
              onBlur={() => setIsSearchFocused(false)}
            />
          </div>
          <button type="button" className="btn btn-secondary" style={{ fontFamily: "var(--font-body)", fontWeight: 400 }} onClick={onUploadClick}>
            {t.uploadPdfBtn}
          </button>
        </div>
      </div>

      {documents.length === 0 ? (
        <p style={{ textAlign: "center", opacity: 0.6, maxWidth: 1100, margin: "var(--space-8) auto" }}>
          {t.emptyLibrary}
        </p>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
            gap: "var(--space-6)",
            maxWidth: 1100,
            margin: "0 auto",
          }}
        >
          {filtered.map((doc) => (
            <div
              key={doc.id}
              className="card elev-sm m-book-card"
              style={{ cursor: "pointer", display: "flex", flexDirection: "column", gap: "var(--space-3)" }}
              onClick={() => onOpenBook(doc.id)}
            >
              <div
                className="plate"
                style={{
                  position: "relative",
                  height: 370,
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: coverTint(doc.title),
                  color: "#F1E7DE",
                  fontFamily: "var(--font-heading)",
                  fontSize: 48,
                }}
              >
                {doc.title.charAt(0).toUpperCase()}
                <button
                  type="button"
                  className="m-book-delete"
                  aria-label={t.deleteBookAria(doc.title)}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (window.confirm(t.confirmDeleteBook(doc.title))) {
                      onDeleteDocument(doc.id);
                    }
                  }}
                >
                  <TrashIcon />
                </button>
              </div>
              <div>
                <div className="card-title" style={{ fontSize: 19, lineHeight: 1.25 }}>
                  {doc.title}
                </div>
                {doc.author && <div style={{ opacity: 0.6, fontSize: 14, marginTop: 2 }}>{doc.author}</div>}
              </div>
              <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
                {doc.total_pages && <span className="tag tag-neutral">{t.pagesLabel(doc.total_pages)}</span>}
                <span className="tag tag-outline">
                  {doc.status !== "ready"
                    ? doc.status
                    : doc.current_page
                      ? t.pageOf(doc.current_page, doc.total_pages ?? doc.current_page)
                      : t.notStarted}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}