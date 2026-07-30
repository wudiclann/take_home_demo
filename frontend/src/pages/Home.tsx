import { useEffect, useState } from "react";
import {
  deleteConversation,
  getOrCreateConversation,
  listDocuments,
  type ConversationOut,
  type DocumentListItem,
} from "../api/client";
import ChatArea from "../components/ChatArea";
import Library from "../components/Library";
import PdfUpload from "../components/PdfUpload";
import SettingsView from "../components/SettingsView";
import Sidebar from "../components/Sidebar";
import { STRINGS, type Language } from "../i18n";

type View = "library" | "settings" | "chat";

export default function Home() {
  const [view, setView] = useState<View>("library");
  const [language, setLanguage] = useState<Language>("en");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [selectedConversation, setSelectedConversation] = useState<ConversationOut | null>(null);
  const [showUpload, setShowUpload] = useState(false);

  const t = STRINGS[language];

  function refreshDocuments() {
    listDocuments().then(setDocuments);
  }

  useEffect(() => {
    refreshDocuments();
  }, []);

  async function openBook(documentId: string) {
    const conversation = await getOrCreateConversation(documentId);
    setSelectedDocumentId(documentId);
    setSelectedConversation(conversation);
    setView("chat");
  }

  async function handleUploaded(documentId: string) {
    setShowUpload(false);
    refreshDocuments();
    await openBook(documentId);
  }

  async function handleDeleteConversation(documentId: string, conversationId: string) {
    await deleteConversation(conversationId);
    if (selectedDocumentId === documentId) {
      setSelectedDocumentId(null);
      setSelectedConversation(null);
      setView("library");
    }
    refreshDocuments();
  }

  function handleConversationUpdate(patch: Partial<ConversationOut>) {
    setSelectedConversation((prev) => (prev ? { ...prev, ...patch } : prev));
    if (patch.current_page !== undefined && selectedDocumentId) {
      setDocuments((prev) =>
        prev.map((d) => (d.id === selectedDocumentId ? { ...d, current_page: patch.current_page ?? d.current_page } : d)),
      );
    }
  }

  const selectedDocument = documents.find((d) => d.id === selectedDocumentId) ?? null;

  return (
    <div style={{ height: "100vh", display: "flex", background: "var(--color-bg)", color: "var(--color-text)", fontFamily: "var(--font-body)" }}>
      <Sidebar
        t={t}
        open={sidebarOpen}
        onToggle={() => setSidebarOpen((v) => !v)}
        view={view}
        documents={documents}
        selectedDocumentId={selectedDocumentId}
        onNewBook={() => setShowUpload(true)}
        onShowLibrary={() => setView("library")}
        onShowSettings={() => setView("settings")}
        onOpenBook={openBook}
        onDeleteConversation={handleDeleteConversation}
      />

      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, position: "relative" }}>
        {view === "library" && <Library t={t} documents={documents} onOpenBook={openBook} onUploadClick={() => setShowUpload(true)} />}
        {view === "settings" && <SettingsView t={t} language={language} onLanguageChange={setLanguage} />}
        {view === "chat" && selectedDocument && selectedConversation && (
          <ChatArea
            t={t}
            documentId={selectedDocument.id}
            documentTitle={selectedDocument.title}
            totalPages={selectedDocument.total_pages}
            conversation={selectedConversation}
            onConversationUpdate={handleConversationUpdate}
          />
        )}
      </div>

      {showUpload && <PdfUpload t={t} onClose={() => setShowUpload(false)} onUploaded={handleUploaded} />}
    </div>
  );
}
