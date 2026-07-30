// fetch wrappers for backend endpoints

export interface DocumentListItem {
  id: string;
  title: string;
  author: string | null;
  total_pages: number | null;
  status: string;
  current_page: number | null;
  conversation_id: string | null;
}

export interface DocumentUploadResponse {
  id: string;
  title: string;
  status: string;
}

export interface DocumentStatusResponse {
  id: string;
  title: string;
  author: string | null;
  status: string;
  total_pages: number | null;
  error_message: string | null;
}

export interface ChapterOut {
  id: string;
  chapter_number: number;
  title: string | null;
  start_page: number | null;
  end_page: number | null;
}

export type AnswerTone = "concise" | "conversational" | "scholarly";

export interface ConversationOut {
  id: string;
  document_id: string;
  title: string | null;
  answer_tone: AnswerTone;
  current_page: number | null;
}

export interface SourceOut {
  chapter_title: string | null;
  start_page: number | null;
  end_page: number | null;
}

export interface ChatResponse {
  message_id: string;
  answer: string;
  is_refusal: boolean;
  top_rerank_score: number | null;
  sources: SourceOut[];
}

export interface AskResponse extends ChatResponse {
  question: string;
  audio_path: string;
}

export interface MessageOut {
  id: string;
  role: "user" | "assistant";
  text: string;
  audio_path: string | null;
  audio_duration_s: number | null;
  top_rerank_score: number | null;
  is_refusal: boolean | null;
  created_at: string;
  sources: SourceOut[];
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // response body wasn't JSON -- fall back to statusText
    }
    throw new Error(detail);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export function listDocuments(): Promise<DocumentListItem[]> {
  return request("/documents");
}

export function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return request("/documents/upload", { method: "POST", body: formData });
}

export function getDocument(id: string): Promise<DocumentStatusResponse> {
  return request(`/documents/${id}`);
}

export function getChapters(id: string): Promise<ChapterOut[]> {
  return request(`/documents/${id}/chapters`);
}

export function pageImageUrl(documentId: string, pageNumber: number): string {
  return `/documents/${documentId}/pages/${pageNumber}`;
}

export function getOrCreateConversation(documentId: string): Promise<ConversationOut> {
  return request(`/documents/${documentId}/conversation`);
}

export function getMessages(conversationId: string): Promise<MessageOut[]> {
  return request(`/conversations/${conversationId}/messages`);
}

export function updateConversation(
  id: string,
  payload: Partial<Pick<ConversationOut, "current_page" | "answer_tone" | "title">>,
): Promise<ConversationOut> {
  return request(`/conversations/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function deleteConversation(id: string): Promise<void> {
  return request(`/conversations/${id}`, { method: "DELETE" });
}

export function sendChatMessage(conversationId: string, question: string): Promise<ChatResponse> {
  return request("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_id: conversationId, question }),
  });
}

export function sendAsk(conversationId: string, audioBlob: Blob): Promise<AskResponse> {
  const formData = new FormData();
  formData.append("conversation_id", conversationId);
  formData.append("file", audioBlob, "question.webm");
  return request("/ask", { method: "POST", body: formData });
}

export async function pollDocumentUntilReady(
  id: string,
  { intervalMs = 1000, maxAttempts = 60 } = {},
): Promise<DocumentStatusResponse> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const doc = await getDocument(id);
    if (doc.status === "ready" || doc.status === "failed") {
      return doc;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error("Document processing timed out");
}
