import { useRef, useState } from "react";
import { pollDocumentUntilReady, uploadDocument } from "../api/client";
import type { Strings } from "../i18n";
import { UploadIcon } from "./icons";

interface PdfUploadProps {
  t: Strings;
  onClose: () => void;
  onUploaded: (documentId: string) => void;
}

export default function PdfUpload({ t, onClose, onUploaded }: PdfUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [status, setStatus] = useState<"idle" | "uploading" | "processing" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function pickFile(candidate: File | undefined) {
    if (!candidate) return;
    if (!candidate.name.toLowerCase().endsWith(".pdf")) {
      setError("Please choose a PDF file.");
      return;
    }
    setError(null);
    setFile(candidate);
  }

  async function handleUpload() {
    if (!file) return;
    setStatus("uploading");
    setError(null);
    try {
      const uploaded = await uploadDocument(file);
      setStatus("processing");
      const finalDoc = await pollDocumentUntilReady(uploaded.id);
      if (finalDoc.status === "failed") {
        setError(finalDoc.error_message ?? "Processing failed.");
        setStatus("error");
        return;
      }
      onUploaded(uploaded.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
      setStatus("error");
    }
  }

  const busy = status === "uploading" || status === "processing";

  return (
    <div className="dialog-backdrop" onClick={busy ? undefined : onClose}>
      <div className="dialog" style={{ width: "min(480px, 100%)", gap: "var(--space-4)" }} onClick={(e) => e.stopPropagation()}>
        <div>
          <div className="dialog-title" style={{ fontSize: 22 }}>
            {t.uploadDialogTitle}
          </div>
          <div style={{ fontSize: 13, opacity: 0.6, marginTop: "var(--space-1)" }}>{t.uploadDialogSubtitle}</div>
        </div>

        <div
          style={{
            border: `1px dashed ${isDragging ? "var(--color-accent)" : "var(--color-neutral-300)"}`,
            borderRadius: "var(--radius-md)",
            padding: "var(--space-8) var(--space-6)",
            textAlign: "center",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "var(--space-4)",
            background: "var(--color-surface)",
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            pickFile(e.dataTransfer.files[0]);
          }}
        >
          <div
            style={{
              width: 52,
              height: 52,
              borderRadius: "50%",
              background: "var(--color-accent-100)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <UploadIcon />
          </div>
          <div>
            <div style={{ fontSize: 15 }}>{file ? file.name : t.dropHere}</div>
            <div style={{ fontSize: 12, opacity: 0.55, marginTop: 2 }}>{t.orBrowse}</div>
          </div>
          <button type="button" className="btn btn-secondary" onClick={() => inputRef.current?.click()} disabled={busy}>
            {t.chooseFile}
          </button>
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf"
            style={{ display: "none" }}
            onChange={(e) => pickFile(e.target.files?.[0])}
          />
          <div style={{ fontSize: 11, opacity: 0.45 }}>{t.pdfHint}</div>
        </div>

        {status === "processing" && (
          <p style={{ fontSize: 13, color: "var(--color-accent-700)", margin: 0 }}>Parsing and indexing…</p>
        )}
        {error && <p style={{ fontSize: 13, color: "var(--color-accent-700)", margin: 0 }}>{error}</p>}

        <div className="dialog-actions" style={{ borderTop: "1px solid var(--color-divider)", paddingTop: "var(--space-4)", marginTop: 0 }}>
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={busy}>
            {t.cancelBtn}
          </button>
          <button type="button" className="btn btn-primary" onClick={handleUpload} disabled={!file || busy}>
            {t.uploadBtn}
          </button>
        </div>
      </div>
    </div>
  );
}
