<template>
  <section :class="['document-library', { 'home-document-library': variant === 'home' }]">
    <div class="document-library-head">
      <label>文档库</label>
      <span>{{ headerText }}</span>
    </div>
    <div class="document-dropzone" :class="{ muted }">
      <strong>{{ dropzoneTitle }}</strong>
      <p>{{ dropzoneHint }}</p>
      <label class="upload-button" :class="{ disabled: uploadDisabled }">
        <input
          type="file"
          accept=".txt,.md,.pdf,.docx,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          :disabled="uploadDisabled"
          @change="$emit('upload', $event)"
        />
        {{ documentLoading ? "上传中..." : "选择文档" }}
      </label>
    </div>
    <p v-if="documentSuccess" class="document-message success">{{ documentSuccess }}</p>
    <p v-if="documentError" class="document-message error">{{ documentError }}</p>
    <p v-if="!documents.length && !documentLoading" class="document-empty">{{ emptyText }}</p>
    <ul v-if="documents.length" class="document-list">
      <li v-for="document in documents" :key="document.id">
        <button
          type="button"
          class="document-item-button"
          :class="{ active: selectedDocumentId === document.id }"
          :aria-expanded="selectedDocumentId === document.id"
          aria-controls="document-detail-panel"
          @click="$emit('select', document.id)"
        >
          <span class="document-name" :title="document.filename">{{ document.filename }}</span>
          <span class="document-meta" :class="document.status">{{ documentStatusText(document) }}</span>
          <span class="document-toggle-mark" aria-hidden="true">⌄</span>
        </button>
      </li>
    </ul>

    <section v-if="selectedDocumentId" id="document-detail-panel" class="document-detail-panel">
      <template v-if="documentDetailLoading">
        <p class="document-empty">正在读取文档详情...</p>
      </template>
      <template v-else-if="selectedDocument">
        <header class="document-detail-header">
          <div>
            <strong :title="selectedDocument.filename">{{ selectedDocument.filename }}</strong>
            <span :class="selectedDocument.status">{{ documentStatusText(selectedDocument) }}</span>
          </div>

          <button
            v-if="selectedDocument.status === 'failed'"
            type="button"
            class="document-delete-btn"
            :disabled="documentRetrying"
            @click="$emit('retry', selectedDocument.id)"
          >
            {{ documentRetrying ? "重试中..." : "重试解析" }}
          </button>
          <button
            type="button"
            class="document-delete-btn"
            :disabled="documentDeleting"
            @click="$emit('delete', selectedDocument.id)"
          >
            {{ documentDeleting ? "删除中..." : "删除" }}
          </button>
        </header>
        <p class="document-preview">{{ documentPreviewText(selectedDocument) }}</p>
        <div class="document-chunks">
          <button
            v-for="chunk in visibleDocumentChunks"
            :key="chunk.id"
            type="button"
            class="document-chunk"
            @click="$emit('toggle-chunk', chunk.id)"
          >
            <span>片段 {{ chunk.chunk_index }}</span>
            <p>{{ expandedChunkIds.has(chunk.id) ? chunk.text : previewText(chunk.text) }}</p>
          </button>
        </div>
      </template>
    </section>
  </section>
</template>

<script lang="ts" setup>
import type { DocumentDetail, DocumentSummary } from "../services/api";

defineProps<{
  variant: "home" | "sidebar";
  headerText: string;
  dropzoneTitle: string;
  dropzoneHint: string;
  emptyText: string;
  muted?: boolean;
  documents: DocumentSummary[];
  documentLoading: boolean;
  documentDetailLoading: boolean;
  documentDeleting: boolean;
  documentRetrying: boolean;
  uploadDisabled: boolean;
  documentSuccess: string;
  documentError: string;
  selectedDocumentId: string | null;
  selectedDocument: DocumentDetail | null;
  visibleDocumentChunks: DocumentDetail["chunks"];
  expandedChunkIds: Set<string>;
  documentStatusText: (document: DocumentSummary | DocumentDetail) => string;
  documentPreviewText: (document: DocumentSummary | DocumentDetail) => string;
  previewText: (value: string | null | undefined, maxLength?: number) => string;
}>();

defineEmits<{
  upload: [event: Event];
  select: [documentId: string];
  retry: [documentId: string];
  delete: [documentId: string];
  "toggle-chunk": [chunkId: string];
}>();
</script>
