// Label-only i18n: swaps interface text (menus/buttons) between English and
// Chinese. Does NOT change ASR/TTS/RAG language capability (English-only) --
// see the "Language" scope decision in CLAUDE.md.

export type Language = "en" | "zh";

export interface Strings {
  appName: string;
  newBook: string;
  library: string;
  settingsNav: string;
  conversations: string;
  answerTone: string;
  toneConcise: string;
  toneConversational: string;
  toneScholarly: string;
  composerPlaceholder: string;
  listening: string;
  libraryTitle: string;
  librarySubtitle: string;
  searchPlaceholder: string;
  uploadPdfBtn: string;
  settingsTitle: string;
  settingsSubtitle: string;
  langLabel: string;
  langDesc: string;
  uploadDialogTitle: string;
  uploadDialogSubtitle: string;
  dropHere: string;
  orBrowse: string;
  chooseFile: string;
  pdfHint: string;
  cancelBtn: string;
  uploadBtn: string;
  pageOf: (page: number, total: number) => string;
  notStarted: string;
  pagesLabel: (n: number) => string;
  refusalFallback: string;
  emptyLibrary: string;
  deleteBookAria: (title: string) => string;
  confirmDeleteBook: (title: string) => string;
  apiKeyLabel: string;
  apiKeyDesc: string;
  apiKeyPlaceholder: string;
  saveKeyBtn: string;
  changeKeyBtn: string;
  cancelKeyChangeBtn: string;
  clearKeyBtn: string;
  confirmClearKey: string;
  keySavedTag: string;
  keySavedToast: string;
  keyClearedToast: string;
  invalidKeyToast: string;
  keyRequiredToast: string;
  voiceSectionLabel: string;
  voiceSectionDesc: string;
  voiceFieldLabel: string;
  speedFieldLabel: string;
  voiceSettingsSavedToast: string;
}

export const STRINGS: Record<Language, Strings> = {
  en: {
    appName: "Take Home Demo",
    newBook: "New book",
    library: "Library",
    settingsNav: "Settings",
    conversations: "Conversations",
    answerTone: "Answer tone",
    toneConcise: "Concise",
    toneConversational: "Conversational",
    toneScholarly: "Scholarly",
    composerPlaceholder: "Ask this book something, or use your voice…",
    listening: "Listening — speak your question…",
    libraryTitle: "Your library",
    librarySubtitle:
      "Ask a book a question aloud, and it answers in its own voice — grounded in its own pages.",
    searchPlaceholder: "Search titles or authors",
    uploadPdfBtn: "Upload PDF",
    settingsTitle: "Settings",
    settingsSubtitle: "Connect your OpenAI key to power transcription and answers. Interface language is separate — voice and retrieval stay English for now.",
    langLabel: "System language",
    langDesc: "Controls the interface language — menus and buttons.",
    uploadDialogTitle: "Add a new book",
    uploadDialogSubtitle: "Upload a PDF and it'll join your library, ready for voice questions.",
    dropHere: "Drag a PDF here",
    orBrowse: "or click to browse your files",
    chooseFile: "Choose file",
    pdfHint: "PDF only · up to 50 MB",
    cancelBtn: "Cancel",
    uploadBtn: "Upload",
    pageOf: (page, total) => `Page ${page} of ${total}`,
    notStarted: "Not started",
    pagesLabel: (n) => `${n} pages`,
    refusalFallback: "No answer found in this book",
    emptyLibrary: "No books yet — upload a PDF to get started.",
    deleteBookAria: (title) => `Delete ${title}`,
    confirmDeleteBook: (title) =>
      `Delete "${title}"? This removes the book, its conversation, and all saved audio.`,
    apiKeyLabel: "OpenAI API key",
    apiKeyDesc:
      "Stored server-side in this app's .env file — used for transcription, retrieval, and voice answers. Never shown again after saving.",
    apiKeyPlaceholder: "sk-…",
    saveKeyBtn: "Save key",
    changeKeyBtn: "Change key",
    cancelKeyChangeBtn: "Cancel",
    clearKeyBtn: "Clear key",
    confirmClearKey: "Remove the saved OpenAI API key? Uploading and asking questions will stop working until a new key is saved.",
    keySavedTag: "Key saved",
    keySavedToast: "OpenAI API key saved.",
    keyClearedToast: "OpenAI API key removed.",
    invalidKeyToast: "That doesn't look like a valid OpenAI API key.",
    keyRequiredToast: "Set up your OpenAI API key in Settings first.",
    voiceSectionLabel: "Answer voice",
    voiceSectionDesc: "Choose the voice and speaking speed used for spoken answers.",
    voiceFieldLabel: "Voice",
    speedFieldLabel: "Speaking speed",
    voiceSettingsSavedToast: "Voice settings saved.",
  },
  zh: {
    appName: "Take Home Demo",
    newBook: "新书",
    library: "书库",
    settingsNav: "设置",
    conversations: "对话",
    answerTone: "回答语气",
    toneConcise: "简洁",
    toneConversational: "对话式",
    toneScholarly: "学术",
    composerPlaceholder: "向这本书提问，或使用语音…",
    listening: "正在聆听——请说出你的问题…",
    libraryTitle: "我的书库",
    librarySubtitle: "对着一本书大声提问，它会用书中的内容亲自回答你。",
    searchPlaceholder: "搜索书名或作者",
    uploadPdfBtn: "上传 PDF",
    settingsTitle: "设置",
    settingsSubtitle: "接入你的 OpenAI 密钥，为转录与回答提供支持。界面语言是独立设置——语音与检索目前仍为英文。",
    langLabel: "系统语言",
    langDesc: "控制界面语言——菜单与按钮。",
    uploadDialogTitle: "添加新书",
    uploadDialogSubtitle: "上传一个 PDF，它将加入你的书库，随时可供语音提问。",
    dropHere: "将 PDF 拖到此处",
    orBrowse: "或点击浏览文件",
    chooseFile: "选择文件",
    pdfHint: "仅支持 PDF · 最大 50 MB",
    cancelBtn: "取消",
    uploadBtn: "上传",
    pageOf: (page, total) => `第 ${page} 页，共 ${total} 页`,
    notStarted: "尚未开始",
    pagesLabel: (n) => `${n} 页`,
    refusalFallback: "未能在本书中找到答案",
    emptyLibrary: "书库还是空的——上传一个 PDF 开始吧。",
    deleteBookAria: (title) => `删除《${title}》`,
    confirmDeleteBook: (title) => `删除《${title}》？这将移除该书、其对话以及所有已保存的音频。`,
    apiKeyLabel: "OpenAI API 密钥",
    apiKeyDesc: "保存在服务器端的 .env 文件中——用于转录、检索与语音回答。保存后将不再显示明文。",
    apiKeyPlaceholder: "sk-…",
    saveKeyBtn: "保存密钥",
    changeKeyBtn: "更改密钥",
    cancelKeyChangeBtn: "取消",
    clearKeyBtn: "清除密钥",
    confirmClearKey: "移除已保存的 OpenAI API 密钥？在保存新密钥之前，上传与提问功能将无法使用。",
    keySavedTag: "密钥已保存",
    keySavedToast: "OpenAI API 密钥已保存。",
    keyClearedToast: "OpenAI API 密钥已移除。",
    invalidKeyToast: "这看起来不是有效的 OpenAI API 密钥。",
    keyRequiredToast: "请先在设置中配置你的 OpenAI API 密钥。",
    voiceSectionLabel: "回答语音",
    voiceSectionDesc: "选择语音回答使用的音色与语速。",
    voiceFieldLabel: "音色",
    speedFieldLabel: "语速",
    voiceSettingsSavedToast: "语音设置已保存。",
  },
};
