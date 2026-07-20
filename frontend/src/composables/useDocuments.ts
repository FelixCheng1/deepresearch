import { computed, ref, type Ref } from "vue";

import {
  deleteDocument,
  getDocument,
  listDocuments,
  retryDocument,
  uploadDocument,
  type DocumentDetail,
  type DocumentSummary
} from "../services/api";

export function useDocuments(isResearchActive: Ref<boolean>, isExpanded: Ref<boolean>) {
  const documents = ref<DocumentSummary[]>([]);
  const documentLoading = ref(false);
  const documentDetailLoading = ref(false);
  const documentDeleting = ref(false);
  const documentRetrying = ref(false);
  const documentError = ref("");
  const documentSuccess = ref("");
  const selectedDocumentId = ref<string | null>(null);
  const selectedDocument = ref<DocumentDetail | null>(null);
  const expandedChunkIds = ref<Set<string>>(new Set());
  let pollTimer: number | null = null;
  let selectionRequestId = 0;

  const visibleDocumentChunks = computed(() =>
    selectedDocument.value?.status === "ready" ? selectedDocument.value.chunks.slice(0, 10) : []
  );
  const uploadDisabled = computed(() => documentLoading.value || (isExpanded.value && isResearchActive.value));
  const sidebarDocumentHint = computed(() => {
    if (documentLoading.value) return "正在上传并解析...";
    if (isResearchActive.value) return "研究进行中暂不上传新文档；新增文档可在下一次研究前加入。";
    return "可查看、删除文档；开始研究前上传的文档会参与本次 RAG 检索。";
  });

  function clearSelectedDocument(): void {
    selectionRequestId += 1;
    selectedDocumentId.value = null;
    selectedDocument.value = null;
    expandedChunkIds.value = new Set();
    documentDetailLoading.value = false;
  }

  function updatePolling(): void {
    const shouldPoll = documents.value.some((document) => document.status === "processing");
    if (shouldPoll && pollTimer === null) {
      pollTimer = window.setInterval(() => { void refreshDocuments(); }, 2000);
    } else if (!shouldPoll && pollTimer !== null) {
      window.clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  async function refreshDocuments(): Promise<void> {
    documentError.value = "";
    try {
      documents.value = await listDocuments();
      updatePolling();
      if (selectedDocumentId.value && documents.value.some((item) => item.id === selectedDocumentId.value)) {
        const latest = documents.value.find((item) => item.id === selectedDocumentId.value);
        if (latest && selectedDocument.value && latest.status !== selectedDocument.value.status) {
          selectedDocument.value = await getDocument(selectedDocumentId.value);
        }
      } else if (selectedDocumentId.value) {
        clearSelectedDocument();
      }
    } catch (error) {
      documentError.value = error instanceof Error ? error.message : "读取文档库失败";
    }
  }

  async function selectDocument(documentId: string): Promise<void> {
    if (selectedDocumentId.value === documentId) {
      clearSelectedDocument();
      return;
    }
    const requestId = ++selectionRequestId;
    selectedDocumentId.value = documentId;
    selectedDocument.value = null;
    expandedChunkIds.value = new Set();
    documentDetailLoading.value = true;
    documentError.value = "";
    try {
      const detail = await getDocument(documentId);
      if (requestId === selectionRequestId && selectedDocumentId.value === documentId) {
        selectedDocument.value = detail;
      }
    } catch (error) {
      if (requestId === selectionRequestId) {
        documentError.value = error instanceof Error ? error.message : "读取文档详情失败";
      }
    } finally {
      if (requestId === selectionRequestId) {
        documentDetailLoading.value = false;
      }
    }
  }

  async function handleRetryDocument(documentId: string): Promise<void> {
    documentRetrying.value = true;
    documentError.value = "";
    documentSuccess.value = "";
    try {
      const document = await retryDocument(documentId);
      documents.value = documents.value.map((item) => item.id === document.id ? document : item);
      selectedDocument.value = await getDocument(documentId);
      documentSuccess.value = `已上传 ${document.filename}，正在后台解析`;
      updatePolling();
    } catch (error) {
      documentError.value = error instanceof Error ? error.message : "重试解析失败";
    } finally {
      documentRetrying.value = false;
    }
  }

  async function handleDeleteDocument(documentId: string): Promise<void> {
    const filename = selectedDocument.value?.filename ?? "该文档";
    if (!window.confirm(`确定删除 ${filename}？删除后对应片段将不再参与 RAG 检索。`)) return;
    documentDeleting.value = true;
    documentError.value = "";
    documentSuccess.value = "";
    try {
      await deleteDocument(documentId);
      documents.value = documents.value.filter((item) => item.id !== documentId);
      clearSelectedDocument();
      documentSuccess.value = `已删除 ${filename}`;
      await refreshDocuments();
    } catch (error) {
      documentError.value = error instanceof Error ? error.message : "删除文档失败";
    } finally {
      documentDeleting.value = false;
    }
  }

  function toggleChunk(chunkId: string): void {
    const next = new Set(expandedChunkIds.value);
    if (next.has(chunkId)) next.delete(chunkId);
    else next.add(chunkId);
    expandedChunkIds.value = next;
  }

  function previewText(value: string | null | undefined, maxLength = 180): string {
    const compact = (value ?? "").replace(/\s+/g, " ").trim();
    if (!compact) return "暂无可预览内容";
    return compact.length > maxLength ? `${compact.slice(0, maxLength).trim()}...` : compact;
  }

  function documentPreviewText(document: DocumentSummary | DocumentDetail): string {
    if (document.status === "processing") return "文档正在解析，完成后会自动进入 RAG 检索。";
    if (document.status === "failed") return document.error_message || "文档解析失败";
    return document.summary || previewText("raw_text" in document ? document.raw_text : "");
  }

  async function handleDocumentUpload(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    if (uploadDisabled.value) {
      input.value = "";
      return;
    }
    const suffix = file.name.split(".").pop()?.toLowerCase();
    if (!suffix || !["txt", "md", "pdf", "docx"].includes(suffix)) {
      documentError.value = "仅支持 .txt、.md、.pdf 和 .docx 文档";
      input.value = "";
      return;
    }
    documentLoading.value = true;
    documentError.value = "";
    documentSuccess.value = "";
    try {
      const document = await uploadDocument(file);
      documents.value = [document, ...documents.value.filter((item) => item.id !== document.id)];
      documentSuccess.value = `已上传 ${document.filename}，正在后台解析`;
      updatePolling();
      clearSelectedDocument();
    } catch (error) {
      documentError.value = error instanceof Error ? error.message : "文档上传失败";
    } finally {
      documentLoading.value = false;
      input.value = "";
    }
  }

  function formatFileSize(size: number): string {
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
  }

  function documentStatusText(document: DocumentSummary | DocumentDetail): string {
    const status = document.status === "processing" ? "解析中" : document.status === "failed" ? "解析失败" : "可检索";
    return `${status} · ${document.chunk_count} 片段 · ${formatFileSize(document.size_bytes)}`;
  }

  function dispose(): void {
    if (pollTimer !== null) {
      window.clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  return {
    documents, documentLoading, documentDetailLoading, documentDeleting,
    documentRetrying, documentError, documentSuccess, selectedDocumentId,
    selectedDocument, expandedChunkIds, visibleDocumentChunks, uploadDisabled,
    sidebarDocumentHint, refreshDocuments, selectDocument, handleRetryDocument,
    handleDeleteDocument, toggleChunk, previewText, documentPreviewText,
    handleDocumentUpload, documentStatusText, dispose
  };
}
