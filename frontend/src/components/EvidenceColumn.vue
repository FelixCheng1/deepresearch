<template>
  <aside class="evidence-column">
    <section class="node-detail-block" v-if="selectedWorkflowNode">
      <h3>节点详情</h3>
      <p class="node-detail-title">{{ selectedWorkflowNode.label }}</p>
      <p class="muted">
        {{ selectedWorkflowNode.detail || formatWorkflowStatus(selectedWorkflowNode.status) }}
      </p>
      <p v-if="selectedWorkflowNode.taskId" class="muted">
        关联任务：{{ selectedWorkflowNode.taskId }} · {{ workflowTaskTitle(selectedWorkflowNode.taskId) }}
      </p>
    </section>

    <section
      class="sources-block"
      :class="{ 'block-highlight': sourcesHighlight }"
    >
      <h3>引用来源</h3>
      <template v-if="currentTaskSources.length">
        <ul class="sources-list">
          <li
            v-for="(item, index) in currentTaskSources"
            :key="`${item.title}-${index}`"
            class="source-item"
            :class="{ 'rag-hit': isDocumentSource(item) }"
          >
            <div class="source-headline">
              <a
                class="source-link"
                :href="item.url || '#'"
                target="_blank"
                rel="noopener noreferrer"
              >
                {{ item.title || item.url || `来源 ${index + 1}` }}
              </a>
              <span v-if="isDocumentSource(item)" class="source-badge">RAG 命中片段</span>
            </div>
            <p v-if="isDocumentSource(item) && (item.snippet || item.raw)" class="source-snippet">
              {{ item.snippet || item.raw }}
            </p>
            <div v-if="item.snippet || item.raw" class="source-tooltip">
              <p v-if="item.snippet">{{ item.snippet }}</p>
              <p v-if="item.raw" class="muted-text">{{ item.raw }}</p>
            </div>
          </li>
        </ul>
      </template>
      <p v-else class="muted">暂无可用来源</p>
    </section>

    <section
      class="tools-block"
      :class="{ 'block-highlight': toolHighlight }"
      v-if="currentTaskToolCalls.length"
    >
      <h3>工具调用记录</h3>
      <ul class="tool-list">
        <li
          v-for="entry in currentTaskToolCalls"
          :key="`${entry.eventId}-${entry.timestamp}`"
          class="tool-entry"
        >
          <div class="tool-entry-header">
            <span class="tool-entry-title">
              #{{ entry.eventId }} {{ entry.agent }} → {{ entry.tool }}
            </span>
            <span
              v-if="entry.noteId"
              class="tool-entry-note"
            >
              笔记：{{ entry.noteId }}
            </span>
          </div>
          <p v-if="entry.notePath" class="tool-entry-path">
            笔记路径：
            <button
              class="link-btn"
              type="button"
              @click="$emit('copy-note-path', entry.notePath)"
            >
              复制
            </button>
            <span class="path-text">{{ entry.notePath }}</span>
          </p>
          <p class="tool-subtitle">参数</p>
          <pre class="tool-pre">{{ formatToolParameters(entry.parameters) }}</pre>
          <template v-if="entry.result">
            <p class="tool-subtitle">执行结果</p>
            <pre class="tool-pre">{{ formatToolResult(entry.result) }}</pre>
          </template>
        </li>
      </ul>
    </section>
  </aside>
</template>

<script lang="ts" setup>
import type { SourceItem, ToolCallLog, WorkflowNodeView } from "../types";

defineProps<{
  selectedWorkflowNode: WorkflowNodeView | null;
  currentTaskSources: SourceItem[];
  currentTaskToolCalls: ToolCallLog[];
  sourcesHighlight: boolean;
  toolHighlight: boolean;
  formatWorkflowStatus: (status: string) => string;
  workflowTaskTitle: (taskId: number | null) => string;
  isDocumentSource: (item: SourceItem) => boolean;
  formatToolParameters: (parameters: Record<string, unknown>) => string;
  formatToolResult: (result: string) => string;
}>();

defineEmits<{
  "copy-note-path": [path: string | null];
}>();
</script>