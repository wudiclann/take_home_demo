import { useMemo, useState } from "react";
import type { DocumentListItem } from "../api/client";
import type { Strings } from "../i18n";

interface LibraryProps {
  t: Strings;
  documents: DocumentListItem[];
  onOpenBook: (documentId: string) => void;
  onUploadClick: () => void;
}

// Deterministic accent-tinted placeholder cover (no real cover art available),
// so cards still read as distinct books rather than identical stock icons.
const COVER_TINTS = ["#7A2333", "#8A6D5C", "#4A392E", "#5E1A27", "#6B5346"];

function coverTint(title: string): string {
  let hash = 0;
  for (const char of title) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return COVER_TINTS[hash % COVER_TINTS.length];
}

export default function Library({ t, documents, onOpenBook, onUploadClick }: LibraryProps) {
  const [query, setQuery] = useState("");

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
          <input
            className="input"
            placeholder={t.searchPlaceholder}
            style={{ width: 240 }}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button type="button" className="btn btn-secondary" onClick={onUploadClick}>
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
            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
            gap: "var(--space-6)",
            maxWidth: 1100,
            margin: "0 auto",
          }}
        >
          {filtered.map((doc) => (
            <div
              key={doc.id}
              className="card elev-sm"
              style={{ cursor: "pointer", display: "flex", flexDirection: "column", gap: "var(--space-3)" }}
              onClick={() => onOpenBook(doc.id)}
            >
              <div
                className="plate"
                style={{
                  aspectRatio: "2/3",
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
