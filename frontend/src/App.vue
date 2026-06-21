<template>
  <main class="app-shell" :class="{ expanded: isExpanded }">
    <div class="aurora" aria-hidden="true">
      <span></span>
      <span></span>
      <span></span>
    </div>

    <!-- 初始状态：居中输入卡片 -->
    <div v-if="!isExpanded" class="layout layout-centered">
      <section class="panel panel-form panel-centered">
        <header class="panel-head">
          <div class="logo">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path
                d="M12 2.5c-.7 0-1.4.2-2 .6L4.6 7C3.6 7.6 3 8.7 3 9.9v4.2c0 1.2.6 2.3 1.6 2.9l5.4 3.9c1.2.8 2.8.8 4 0l5.4-3.9c1-.7 1.6-1.7 1.6-2.9V9.9c0-1.2-.6-2.3-1.6-2.9L14 3.1a3.6 3.6 0 0 0-2-.6Z"
              />
            </svg>
          </div>
          <div>
            <h1>深度研究助手</h1>
            <p>结合多轮智能检索与总结，实时呈现洞见与引用。</p>
          </div>
        </header>

        <form class="form" @submit.prevent="handleSubmit">
          <label class="field">
            <span>研究主题</span>
            <textarea
              v-model="form.topic"
              placeholder="例如：探索多模态模型在 2025 年的关键突破"
              rows="4"
              required
            ></textarea>
          </label>

          <section class="options">
            <label class="field option">
              <span>搜索引擎</span>
              <select v-model="form.searchApi">
                <option value="">沿用后端配置</option>
                <option
                  v-for="option in searchOptions"
                  :key="option"
                  :value="option"
                >
                  {{ option }}
                </option>
              </select>
            </label>
          </section>

          <section class="home-document-library document-library">
            <div class="document-library-head">
              <label>文档库</label>
              <span>{{ documents.length ? `${documents.length} 个文档可检索` : "未上传文档" }}</span>
            </div>
            <div class="document-dropzone">
              <strong>{{ documents.length ? "研究将优先检索这些文档" : "先上传研究文档" }}</strong>
              <p>{{ documentLoading ? "正在上传并解析..." : "支持 .txt / .md / .pdf / .docx，上传后会后台解析并进入 RAG 检索。" }}</p>
              <label class="upload-button" :class="{ disabled: uploadDisabled }">
                <input
                  type="file"
                  accept=".txt,.md,.pdf,.docx,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  :disabled="uploadDisabled"
                  @change="handleDocumentUpload"
                />
                {{ documentLoading ? "上传中..." : "选择文档" }}
              </label>
            </div>
            <p v-if="documentSuccess" class="document-message success">{{ documentSuccess }}</p>
            <p v-if="documentError" class="document-message error">{{ documentError }}</p>
            <p v-if="!documents.length && !documentLoading" class="document-empty">暂无文档，仍可直接开始研究。</p>
            <ul v-if="documents.length" class="document-list">
              <li v-for="document in documents" :key="document.id">
                <button
                  type="button"
                  class="document-item-button"
                  :class="{ active: selectedDocumentId === document.id }"
                  @click="selectDocument(document.id)"
                >
                  <span class="document-name" :title="document.filename">{{ document.filename }}</span>
                  <span class="document-meta">{{ document.chunk_count }} 片段 · {{ formatFileSize(document.size_bytes) }}</span>
                </button>
              </li>
            </ul>

            <section v-if="selectedDocumentId" class="document-detail-panel">
              <template v-if="documentDetailLoading">
                <p class="document-empty">正在读取文档详情...</p>
              </template>
              <template v-else-if="selectedDocument">
                <header class="document-detail-header">
                  <div>
                    <strong :title="selectedDocument.filename">{{ selectedDocument.filename }}</strong>
                    <span>{{ selectedDocument.chunk_count }} 片段 · {{ formatFileSize(selectedDocument.size_bytes) }}</span>
                  </div>

                  <button
                    v-if="selectedDocument.status === 'failed'"
                    type="button"
                    class="document-delete-btn"
                    :disabled="documentRetrying"
                    @click="handleRetryDocument(selectedDocument.id)"
                  >
                    {{ documentRetrying ? "重试中..." : "重试解析" }}
                  </button>
                  <button
                    type="button"
                    class="document-delete-btn"
                    :disabled="documentDeleting"
                    @click="handleDeleteDocument(selectedDocument.id)"
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
                    @click="toggleChunk(chunk.id)"
                  >
                    <span>片段 {{ chunk.chunk_index }}</span>
                    <p>{{ expandedChunkIds.has(chunk.id) ? chunk.text : previewText(chunk.text) }}</p>
                  </button>
                </div>
              </template>
            </section>
          </section>
          <div class="form-actions">
            <button class="submit" type="submit" :disabled="loading">
              <span class="submit-label">
                <svg
                  v-if="loading"
                  class="spinner"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <circle cx="12" cy="12" r="9" stroke-width="3" />
                </svg>
                {{ loading ? "研究进行中..." : "开始研究" }}
              </span>
            </button>
            <button
              v-if="loading"
              type="button"
              class="secondary-btn"
              @click="cancelResearch"
            >
              取消研究
            </button>
          </div>
        </form>

        <p v-if="error" class="error-chip">
          <svg viewBox="0 0 20 20" aria-hidden="true">
            <path
              d="M10 3.2c-.3 0-.6.2-.8.5L3.4 15c-.4.7.1 1.6.8 1.6h11.6c.7 0 1.2-.9.8-1.6L10.8 3.7c-.2-.3-.5-.5-.8-.5Zm0 4.3c.4 0 .7.3.7.7v4c0 .4-.3.7-.7.7s-.7-.3-.7-.7V8.2c0-.4.3-.7.7-.7Zm0 6.6a1 1 0 1 1 0 2 1 1 0 0 1 0-2Z"
            />
          </svg>
          {{ error }}
        </p>
        <p v-else-if="loading" class="hint muted">
          正在收集线索与证据，实时进展见右侧区域。
        </p>
      </section>
    </div>

    <!-- 全屏状态：左右分栏布局 -->
    <div v-else class="layout layout-fullscreen">
      <!-- 左侧：研究信息 -->
      <aside class="sidebar">
        <div class="sidebar-header">
          <button class="back-btn" @click="goBack" :disabled="loading">
            <svg viewBox="0 0 24 24" width="20" height="20">
              <path d="M19 12H5M12 19l-7-7 7-7" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            返回
          </button>
          <h2>🔍 深度研究助手</h2>
        </div>

        <div class="research-info">
          <div class="info-item">
            <label>研究主题</label>
            <p class="topic-display">{{ form.topic }}</p>
          </div>

          <div class="info-item" v-if="form.searchApi">
            <label>搜索引擎</label>
            <p>{{ form.searchApi }}</p>
          </div>

          <div class="info-item" v-if="totalTasks > 0">
            <label>研究进度</label>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: `${(completedTasks / totalTasks) * 100}%` }"></div>
            </div>
            <p class="progress-text">{{ completedTasks }} / {{ totalTasks }} 任务完成</p>
          </div>

          <div class="info-item document-library">
            <div class="document-library-head">
              <label>文档库</label>
              <span>本次启动时 {{ researchDocumentCount }} 个文档可检索</span>
            </div>
            <div class="document-dropzone" :class="{ muted: loading }">
              <strong>{{ documents.length ? `${documents.length} 个文档在库` : "暂无文档" }}</strong>
              <p>{{ sidebarDocumentHint }}</p>
              <label class="upload-button" :class="{ disabled: uploadDisabled }">
                <input
                  type="file"
                  accept=".txt,.md,.pdf,.docx,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  :disabled="uploadDisabled"
                  @change="handleDocumentUpload"
                />
                {{ documentLoading ? "上传中..." : "选择文档" }}
              </label>
            </div>
            <p v-if="documentSuccess" class="document-message success">{{ documentSuccess }}</p>
            <p v-if="documentError" class="document-message error">{{ documentError }}</p>
            <p v-if="!documents.length && !documentLoading" class="document-empty">暂无文档</p>
            <ul v-if="documents.length" class="document-list">
              <li v-for="document in documents" :key="document.id">
                <button
                  type="button"
                  class="document-item-button"
                  :class="{ active: selectedDocumentId === document.id }"
                  @click="selectDocument(document.id)"
                >
                  <span class="document-name" :title="document.filename">{{ document.filename }}</span>
                  <span class="document-meta">{{ document.chunk_count }} 片段 · {{ formatFileSize(document.size_bytes) }}</span>
                </button>
              </li>
            </ul>

            <section v-if="selectedDocumentId" class="document-detail-panel">
              <template v-if="documentDetailLoading">
                <p class="document-empty">正在读取文档详情...</p>
              </template>
              <template v-else-if="selectedDocument">
                <header class="document-detail-header">
                  <div>
                    <strong :title="selectedDocument.filename">{{ selectedDocument.filename }}</strong>
                    <span>{{ selectedDocument.chunk_count }} 片段 · {{ formatFileSize(selectedDocument.size_bytes) }}</span>
                  </div>

                  <button
                    v-if="selectedDocument.status === 'failed'"
                    type="button"
                    class="document-delete-btn"
                    :disabled="documentRetrying"
                    @click="handleRetryDocument(selectedDocument.id)"
                  >
                    {{ documentRetrying ? "重试中..." : "重试解析" }}
                  </button>
                  <button
                    type="button"
                    class="document-delete-btn"
                    :disabled="documentDeleting"
                    @click="handleDeleteDocument(selectedDocument.id)"
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
                    @click="toggleChunk(chunk.id)"
                  >
                    <span>片段 {{ chunk.chunk_index }}</span>
                    <p>{{ expandedChunkIds.has(chunk.id) ? chunk.text : previewText(chunk.text) }}</p>
                  </button>
                </div>
              </template>
            </section>
          </div>
        </div>

        <div class="sidebar-actions">
          <button class="new-research-btn" @click="startNewResearch">
            <svg viewBox="0 0 24 24" width="18" height="18">
              <path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>
            </svg>
            开始新研究
          </button>
        </div>
      </aside>

      <!-- 右侧：研究结果 -->
      <section
        class="panel panel-result"
        v-if="todoTasks.length || reportMarkdown || progressLogs.length"
      >
        <header class="status-bar">
          <div class="status-main">
            <div class="status-chip" :class="{ active: loading }">
              <span class="dot"></span>
              {{ loading ? "研究进行中" : "研究流程完成" }}
            </div>
            <span class="status-meta">
              任务进度：{{ completedTasks }} / {{ totalTasks || todoTasks.length || 1 }}
              · 阶段记录 {{ progressLogs.length }} 条
            </span>
          </div>
          <div class="status-controls">
            <button class="secondary-btn" @click="logsCollapsed = !logsCollapsed">
              {{ logsCollapsed ? "展开流程" : "收起流程" }}
            </button>
          </div>
        </header>

        <div class="timeline-wrapper" v-show="!logsCollapsed && progressLogs.length">
          <transition-group name="timeline" tag="ul" class="timeline">
            <li v-for="(log, index) in progressLogs" :key="`${log}-${index}`">
              <span class="timeline-node"></span>
              <p>{{ log }}</p>
            </li>
          </transition-group>
        </div>

        <div class="result-workbench">
          <div class="content-column">
            <section class="workflow-panel">
              <div class="workflow-panel-header">
                <div>
                  <h3>LangGraph 并行工作流</h3>
                  <p>{{ completedWorkflowNodes }} / {{ visibleWorkflowNodes.length }} 节点完成 · {{ workflowEdges.length }} 条边</p>
                </div>
              </div>
              <div class="workflow-map" role="list" aria-label="LangGraph 节点图">
                <div class="workflow-global-row">
                  <button
                    v-for="node in globalWorkflowNodes"
                    :key="node.key"
                    type="button"
                    :class="['graph-node', node.status, { selected: node.id === selectedWorkflowNodeId }]"
                    @click="selectedWorkflowNodeId = node.id"
                  >
                    <span class="graph-node-dot"></span>
                    <strong>{{ node.label }}</strong>
                    <small>{{ node.detail || formatWorkflowStatus(node.status) }}</small>
                  </button>
                </div>

                <div class="workflow-lanes" v-if="taskWorkflowRows.length">
                  <section
                    v-for="row in taskWorkflowRows"
                    :key="row.task.id"
                    class="workflow-lane"
                  >
                    <button
                      type="button"
                      class="workflow-lane-label"
                      @click="activeTaskId = row.task.id"
                    >
                      <span>任务 {{ row.task.id }}</span>
                      <strong>{{ row.task.title }}</strong>
                    </button>
                    <div class="workflow-lane-nodes">
                      <button
                        v-for="node in row.nodes"
                        :key="node.key"
                        type="button"
                        :class="['graph-node', 'task-node', node.status, { selected: node.id === selectedWorkflowNodeId }]"
                        @click="selectedWorkflowNodeId = node.id; activeTaskId = node.taskId"
                      >
                        <span class="graph-node-dot"></span>
                        <strong>{{ node.label }}</strong>
                        <small>{{ node.detail || formatWorkflowStatus(node.status) }}</small>
                      </button>
                    </div>
                  </section>
                </div>

                <div class="workflow-global-row report-row">
                  <button
                    v-for="node in reportWorkflowNodes"
                    :key="node.key"
                    type="button"
                    :class="['graph-node', node.status, { selected: node.id === selectedWorkflowNodeId }]"
                    @click="selectedWorkflowNodeId = node.id"
                  >
                    <span class="graph-node-dot"></span>
                    <strong>{{ node.label }}</strong>
                    <small>{{ node.detail || formatWorkflowStatus(node.status) }}</small>
                  </button>
                </div>
              </div>
            </section>

            <div class="tasks-section" v-if="todoTasks.length">
              <aside class="tasks-list">
                <h3>任务清单</h3>
                <ul>
                  <li
                    v-for="task in todoTasks"
                    :key="task.id"
                    :class="['task-item', { active: task.id === activeTaskId, completed: task.status === 'completed' }]"
                  >
                    <button
                      type="button"
                      class="task-button"
                      @click="activeTaskId = task.id"
                    >
                      <span class="task-title">{{ task.title }}</span>
                      <span class="task-status" :class="task.status">
                        {{ formatTaskStatus(task.status) }}
                      </span>
                    </button>
                    <p class="task-intent">{{ task.intent }}</p>
                  </li>
                </ul>
              </aside>

              <article class="task-detail" v-if="currentTask">
                <header class="task-header">
                  <div>
                    <h3>{{ currentTaskTitle || "当前任务" }}</h3>
                    <p class="muted" v-if="currentTaskIntent">
                      {{ currentTaskIntent }}
                    </p>
                  </div>
                  <div class="task-chip-group">
                    <span class="task-label">查询：{{ currentTaskQuery || "" }}</span>
                    <span
                      v-if="currentTaskNoteId"
                      class="task-label note-chip"
                      :title="currentTaskNoteId"
                    >
                      笔记：{{ currentTaskNoteId }}
                    </span>
                    <span
                      v-if="currentTaskNotePath"
                      class="task-label note-chip path-chip"
                      :title="currentTaskNotePath"
                    >
                      <span class="path-label">路径：</span>
                      <span class="path-text">{{ currentTaskNotePath }}</span>
                      <button
                        class="chip-action"
                        type="button"
                        @click="copyNotePath(currentTaskNotePath)"
                      >
                        复制
                      </button>
                    </span>
                  </div>
                </header>

                <section v-if="currentTask && currentTask.notices.length" class="task-notices">
                  <h4>系统提示</h4>
                  <ul>
                    <li v-for="(notice, idx) in currentTask.notices" :key="`${notice}-${idx}`">
                      {{ notice }}
                    </li>
                  </ul>
                </section>

                <section
                  class="summary-block"
                  :class="{ 'block-highlight': summaryHighlight }"
                >
                  <h3>任务总结</h3>
                  <pre class="block-pre">{{ currentTaskSummary || "暂无可用信息" }}</pre>
                </section>
              </article>

              <article class="task-detail" v-else>
                <p class="muted">等待任务规划或执行结果。</p>
              </article>
            </div>

            <section
              v-if="reportMarkdown"
              class="report-block report-block-main"
              :class="{ 'block-highlight': reportHighlight }"
            >
              <h3>最终报告</h3>
              <pre class="block-pre">{{ reportMarkdown }}</pre>
            </section>
          </div>

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
                  >
                    <a
                      class="source-link"
                      :href="item.url || '#'"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {{ item.title || item.url || `来源 ${index + 1}` }}
                    </a>
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
                      @click="copyNotePath(entry.notePath)"
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
        </div>
      </section>

    </div>
  </main>
</template>

<script lang="ts" setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";

import {
  deleteDocument,
  getDocument,
  listDocuments,
  retryDocument,
  runResearchStream,
  uploadDocument,
  type DocumentDetail,
  type DocumentSummary,
  type ResearchStreamEvent
} from "./services/api";

interface SourceItem {
  title: string;
  url: string;
  snippet: string;
  raw: string;
}

interface ToolCallLog {
  eventId: number;
  agent: string;
  tool: string;
  parameters: Record<string, unknown>;
  result: string;
  noteId: string | null;
  notePath: string | null;
  timestamp: number;
}

interface TodoTaskView {
  id: number;
  title: string;
  intent: string;
  query: string;
  status: string;
  summary: string;
  sourcesSummary: string;
  sourceItems: SourceItem[];
  notices: string[];
  noteId: string | null;
  notePath: string | null;
  toolCalls: ToolCallLog[];
}

interface WorkflowNodeView {
  key: string;
  id: string;
  node: string;
  label: string;
  status: string;
  detail: string;
  scope: string;
  taskId: number | null;
  taskTitle: string;
  dependsOn: string[];
}

interface WorkflowEdgeView {
  from: string;
  to: string;
}

const form = reactive({
  topic: "",
  searchApi: ""
});

const loading = ref(false);
const error = ref("");
const progressLogs = ref<string[]>([]);
const logsCollapsed = ref(false);
const isExpanded = ref(false);

const todoTasks = ref<TodoTaskView[]>([]);
const activeTaskId = ref<number | null>(null);
const reportMarkdown = ref("");
const workflowNodes = ref<WorkflowNodeView[]>([]);
const workflowEdges = ref<WorkflowEdgeView[]>([]);
const selectedWorkflowNodeId = ref<string | null>(null);

const summaryHighlight = ref(false);
const sourcesHighlight = ref(false);
const reportHighlight = ref(false);
const toolHighlight = ref(false);

const documents = ref<DocumentSummary[]>([]);
const documentLoading = ref(false);
const documentDetailLoading = ref(false);
const documentDeleting = ref(false);
const documentRetrying = ref(false);
const documentError = ref("");
const documentSuccess = ref("");
const researchDocumentCount = ref(0);
const selectedDocumentId = ref<string | null>(null);
const selectedDocument = ref<DocumentDetail | null>(null);
const expandedChunkIds = ref<Set<string>>(new Set());

let currentController: AbortController | null = null;
let documentPollTimer: number | null = null;

const searchOptions = [
  "advanced",
  "duckduckgo",
  "tavily",
  "perplexity",
  "searxng"
];

const TASK_STATUS_LABEL: Record<string, string> = {
  pending: "待执行",
  in_progress: "进行中",
  completed: "已完成",
  skipped: "已跳过"
};

const WORKFLOW_STATUS_LABEL: Record<string, string> = {
  pending: "等待中",
  in_progress: "执行中",
  completed: "已完成",
  skipped: "已跳过",
  failed: "失败"
};

const defaultWorkflowNodes: WorkflowNodeView[] = [
  { key: "global:plan_tasks", id: "global:plan_tasks", node: "plan_tasks", label: "规划研究任务", status: "pending", detail: "", scope: "global", taskId: null, taskTitle: "", dependsOn: [] },
  { key: "global:dispatch_tasks", id: "global:dispatch_tasks", node: "dispatch_tasks", label: "分发并行任务", status: "pending", detail: "", scope: "global", taskId: null, taskTitle: "", dependsOn: ["global:plan_tasks"] },
  { key: "global:join_tasks", id: "global:join_tasks", node: "join_tasks", label: "汇总任务结果", status: "pending", detail: "", scope: "global", taskId: null, taskTitle: "", dependsOn: [] },
  { key: "global:write_report", id: "global:write_report", node: "write_report", label: "撰写最终报告", status: "pending", detail: "", scope: "global", taskId: null, taskTitle: "", dependsOn: ["global:join_tasks"] },
  { key: "global:persist_report", id: "global:persist_report", node: "persist_report", label: "保存最终报告", status: "pending", detail: "", scope: "global", taskId: null, taskTitle: "", dependsOn: ["global:write_report"] }
];

function formatTaskStatus(status: string): string {
  return TASK_STATUS_LABEL[status] ?? status;
}

function formatWorkflowStatus(status: string): string {
  return WORKFLOW_STATUS_LABEL[status] ?? status;
}

function workflowTaskTitle(taskId: number | null): string {
  if (!taskId) {
    return "全局流程";
  }
  return todoTasks.value.find((task) => task.id === taskId)?.title ?? "任务";
}

const totalTasks = computed(() => todoTasks.value.length);
const completedTasks = computed(() =>
  todoTasks.value.filter((task) => task.status === "completed").length
);
const visibleWorkflowNodes = computed(() =>
  workflowNodes.value.length ? workflowNodes.value : defaultWorkflowNodes
);
const completedWorkflowNodes = computed(
  () =>
    visibleWorkflowNodes.value.filter((node) =>
      ["completed", "skipped"].includes(node.status)
    ).length
);

const globalWorkflowNodes = computed(() =>
  visibleWorkflowNodes.value.filter((node) =>
    node.scope === "global" && ["plan_tasks", "dispatch_tasks"].includes(node.node)
  )
);

const reportWorkflowNodes = computed(() =>
  visibleWorkflowNodes.value.filter((node) =>
    node.scope === "global" && ["join_tasks", "write_report", "persist_report"].includes(node.node)
  )
);

const taskWorkflowRows = computed(() =>
  todoTasks.value.map((task) => ({
    task,
    nodes: visibleWorkflowNodes.value.filter((node) => node.taskId === task.id)
  }))
);

const selectedWorkflowNode = computed(() => {
  if (!selectedWorkflowNodeId.value) {
    return null;
  }
  return visibleWorkflowNodes.value.find((node) => node.id === selectedWorkflowNodeId.value) ?? null;
});

const currentTask = computed(() => {
  if (activeTaskId.value !== null) {
    return todoTasks.value.find((task) => task.id === activeTaskId.value) ?? null;
  }
  return todoTasks.value[0] ?? null;
});

const currentTaskSources = computed(() => currentTask.value?.sourceItems ?? []);
const currentTaskSummary = computed(() => currentTask.value?.summary ?? "");
const currentTaskTitle = computed(() => currentTask.value?.title ?? "");
const currentTaskIntent = computed(() => currentTask.value?.intent ?? "");
const currentTaskQuery = computed(() => currentTask.value?.query ?? "");
const currentTaskNoteId = computed(() => currentTask.value?.noteId ?? "");
const currentTaskNotePath = computed(() => currentTask.value?.notePath ?? "");
const currentTaskToolCalls = computed(
  () => currentTask.value?.toolCalls ?? []
);

const pulse = (flag: typeof summaryHighlight) => {
  flag.value = false;
  requestAnimationFrame(() => {
    flag.value = true;
    window.setTimeout(() => {
      flag.value = false;
    }, 1200);
  });
};

function parseSources(raw: string): SourceItem[] {
  if (!raw) {
    return [];
  }

  const items: SourceItem[] = [];
  const lines = raw.split("\n");

  let current: SourceItem | null = null;
  const truncate = (value: string, max = 360) => {
    const trimmed = value.trim();
    return trimmed.length > max ? `${trimmed.slice(0, max)}…` : trimmed;
  };

  const flush = () => {
    if (!current) {
      return;
    }
    const normalized: SourceItem = {
      title: current.title?.trim() || "",
      url: current.url?.trim() || "",
      snippet: current.snippet ? truncate(current.snippet) : "",
      raw: current.raw ? truncate(current.raw, 420) : ""
    };

    if (
      normalized.title ||
      normalized.url ||
      normalized.snippet ||
      normalized.raw
    ) {
      if (!normalized.title && normalized.url) {
        normalized.title = normalized.url;
      }
      items.push(normalized);
    }
    current = null;
  };

  const ensureCurrent = () => {
    if (!current) {
      current = { title: "", url: "", snippet: "", raw: "" };
    }
  };

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      continue;
    }

    if (/^\*/.test(trimmed) && trimmed.includes(" : ")) {
      flush();
      const withoutBullet = trimmed.replace(/^\*\s*/, "");
      const [titlePart, urlPart] = withoutBullet.split(" : ");
      current = {
        title: titlePart?.trim() || "",
        url: urlPart?.trim() || "",
        snippet: "",
        raw: ""
      };
      continue;
    }

    if (/^(Source|信息来源)\s*:/.test(trimmed)) {
      flush();
      const [, titlePart = ""] = trimmed.split(/:\s*(.+)/);
      current = {
        title: titlePart.trim(),
        url: "",
        snippet: "",
        raw: ""
      };
      continue;
    }

    if (/^URL\s*:/.test(trimmed)) {
      ensureCurrent();
      const [, urlPart = ""] = trimmed.split(/:\s*(.+)/);
      current!.url = urlPart.trim();
      continue;
    }

    if (
      /^(Most relevant content from source|信息内容)\s*:/.test(trimmed)
    ) {
      ensureCurrent();
      const [, contentPart = ""] = trimmed.split(/:\s*(.+)/);
      current!.snippet = contentPart.trim();
      continue;
    }

    if (
      /^(Full source content limited to|信息内容限制为)\s*:/.test(trimmed)
    ) {
      ensureCurrent();
      const [, rawPart = ""] = trimmed.split(/:\s*(.+)/);
      current!.raw = rawPart.trim();
      continue;
    }

    if (/^https?:\/\//.test(trimmed)) {
      ensureCurrent();
      if (!current!.url) {
        current!.url = trimmed;
        continue;
      }
    }

    ensureCurrent();
    current!.raw = current!.raw ? `${current!.raw}\n${trimmed}` : trimmed;
  }

  flush();
  return items;
}

function extractOptionalString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function ensureRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function applyNoteMetadata(
  task: TodoTaskView,
  payload: Record<string, unknown>
): void {
  const noteId = extractOptionalString(payload.note_id);
  if (noteId) {
    task.noteId = noteId;
  }
  const notePath = extractOptionalString(payload.note_path);
  if (notePath) {
    task.notePath = notePath;
  }
}

function formatToolParameters(parameters: Record<string, unknown>): string {
  try {
    return JSON.stringify(parameters, null, 2);
  } catch (error) {
    console.warn("无法格式化工具参数", error, parameters);
    return Object.entries(parameters)
      .map(([key, value]) => `${key}: ${String(value)}`)
      .join("\n");
  }
}

function formatToolResult(result: string): string {
  const trimmed = result.trim();
  const limit = 900;
  if (trimmed.length > limit) {
    return `${trimmed.slice(0, limit)}…`;
  }
  return trimmed;
}

async function copyNotePath(path: string | null | undefined) {
  if (!path) {
    return;
  }

  try {
    await navigator.clipboard.writeText(path);
    progressLogs.value.push(`已复制笔记路径：${path}`);
  } catch (error) {
    console.warn("无法直接复制到剪贴板", error);
    window.prompt("复制以下笔记路径", path);
    progressLogs.value.push("请手动复制笔记路径");
  }
}

function resetWorkflowState() {
  todoTasks.value = [];
  activeTaskId.value = null;
  reportMarkdown.value = "";
  workflowNodes.value = [];
  workflowEdges.value = [];
  selectedWorkflowNodeId.value = null;
  progressLogs.value = [];
  summaryHighlight.value = false;
  sourcesHighlight.value = false;
  reportHighlight.value = false;
  toolHighlight.value = false;
  logsCollapsed.value = false;
}

function findTask(taskId: unknown): TodoTaskView | undefined {
  const numeric =
    typeof taskId === "number"
      ? taskId
      : typeof taskId === "string"
      ? Number(taskId)
      : NaN;
  if (Number.isNaN(numeric)) {
    return undefined;
  }
  return todoTasks.value.find((task) => task.id === numeric);
}

function upsertTaskMetadata(task: TodoTaskView, payload: Record<string, unknown>) {
  if (typeof payload.title === "string" && payload.title.trim()) {
    task.title = payload.title.trim();
  }
  if (typeof payload.intent === "string" && payload.intent.trim()) {
    task.intent = payload.intent.trim();
  }
  if (typeof payload.query === "string" && payload.query.trim()) {
    task.query = payload.query.trim();
  }
}

function upsertWorkflowNode(payload: Record<string, unknown>) {
  const node = extractOptionalString(payload.node);
  if (!node) {
    return;
  }
  const nodeId = extractOptionalString(payload.node_id) ?? "";
  const label = extractOptionalString(payload.label) ?? node;
  const status = extractOptionalString(payload.status) ?? "pending";
  const detail = extractOptionalString(payload.detail) ?? "";
  const scope = extractOptionalString(payload.scope) ?? "global";
  const dependsOn = Array.isArray(payload.depends_on)
    ? payload.depends_on.filter((item): item is string => typeof item === "string")
    : [];
  const rawTaskId = payload.task_id;
  const taskId =
    typeof rawTaskId === "number"
      ? rawTaskId
      : typeof rawTaskId === "string"
      ? Number(rawTaskId)
      : null;
  const normalizedTaskId =
    typeof taskId === "number" && Number.isFinite(taskId) ? taskId : null;
  const taskTitle = normalizedTaskId ? workflowTaskTitle(normalizedTaskId) : "";
  const key = nodeId || `${scope}:${normalizedTaskId ?? "global"}:${node}`;
  const existing = workflowNodes.value.find((item) => item.key === key);
  if (existing) {
    existing.id = key;
    existing.label = label;
    existing.status = status;
    existing.detail = detail;
    existing.scope = scope;
    existing.taskId = normalizedTaskId;
    existing.taskTitle = taskTitle;
    existing.dependsOn = dependsOn;
  } else {
    workflowNodes.value.push({
      key,
      id: key,
      node,
      label,
      status,
      detail,
      scope,
      taskId: normalizedTaskId,
      taskTitle,
      dependsOn
    });
  }
}

function applyWorkflowGraph(payload: Record<string, unknown>) {
  const nodes = Array.isArray(payload.nodes)
    ? (payload.nodes as Record<string, unknown>[])
    : [];
  const edges = Array.isArray(payload.edges)
    ? (payload.edges as Record<string, unknown>[])
    : [];

  workflowNodes.value = nodes.map((item) => {
    const id =
      extractOptionalString(item.id) ??
      extractOptionalString(item.node) ??
      `node-${workflowNodes.value.length}-${Date.now()}`;
    const rawTaskId = item.task_id;
    const taskId =
      typeof rawTaskId === "number"
        ? rawTaskId
        : typeof rawTaskId === "string"
        ? Number(rawTaskId)
        : null;
    const normalizedTaskId =
      typeof taskId === "number" && Number.isFinite(taskId) ? taskId : null;

    return {
      key: id,
      id,
      node: extractOptionalString(item.node) ?? id,
      label: extractOptionalString(item.label) ?? id,
      status: extractOptionalString(item.status) ?? "pending",
      detail: "",
      scope: extractOptionalString(item.scope) ?? "global",
      taskId: normalizedTaskId,
      taskTitle: extractOptionalString(item.task_title) ?? workflowTaskTitle(normalizedTaskId),
      dependsOn: []
    };
  });

  workflowEdges.value = edges
    .map((item) => ({
      from: extractOptionalString(item.from) ?? "",
      to: extractOptionalString(item.to) ?? ""
    }))
    .filter((edge) => edge.from && edge.to);
}

async function refreshDocuments() {
  documentError.value = "";
  try {
    documents.value = await listDocuments();
    updateDocumentPolling();
    if (selectedDocumentId.value && documents.value.some((item) => item.id === selectedDocumentId.value)) {
      const latest = documents.value.find((item) => item.id === selectedDocumentId.value);
      if (latest && selectedDocument.value && latest.status !== selectedDocument.value.status) {
        selectedDocument.value = await getDocument(selectedDocumentId.value);
      }
    }
    if (
      selectedDocumentId.value &&
      !documents.value.some((item) => item.id === selectedDocumentId.value)
    ) {
      clearSelectedDocument();
    }
  } catch (err) {
    documentError.value = err instanceof Error ? err.message : "读取文档库失败";
  }
}

async function selectDocument(documentId: string) {
  selectedDocumentId.value = documentId;
  selectedDocument.value = null;
  expandedChunkIds.value = new Set();
  documentDetailLoading.value = true;
  documentError.value = "";
  try {
    selectedDocument.value = await getDocument(documentId);
  } catch (err) {
    documentError.value = err instanceof Error ? err.message : "读取文档详情失败";
  } finally {
    documentDetailLoading.value = false;
  }
}

async function handleRetryDocument(documentId: string) {
  documentRetrying.value = true;
  documentError.value = "";
  documentSuccess.value = "";
  try {
    const document = await retryDocument(documentId);
    documents.value = documents.value.map((item) => item.id === document.id ? document : item);
    selectedDocument.value = await getDocument(documentId);
    documentSuccess.value = `已上传 ${document.filename}，正在后台解析`;
    updateDocumentPolling();
  } catch (err) {
    documentError.value = err instanceof Error ? err.message : "重试解析失败";
  } finally {
    documentRetrying.value = false;
  }
}

async function handleDeleteDocument(documentId: string) {
  const target = selectedDocument.value;
  const filename = target?.filename ?? "该文档";
  if (!window.confirm(`确定删除 ${filename}？删除后对应片段将不再参与 RAG 检索。`)) {
    return;
  }

  documentDeleting.value = true;
  documentError.value = "";
  documentSuccess.value = "";
  try {
    await deleteDocument(documentId);
    documents.value = documents.value.filter((item) => item.id !== documentId);
    clearSelectedDocument();
    documentSuccess.value = `已删除 ${filename}`;
    await refreshDocuments();
  } catch (err) {
    documentError.value = err instanceof Error ? err.message : "删除文档失败";
  } finally {
    documentDeleting.value = false;
  }
}

function clearSelectedDocument() {
  selectedDocumentId.value = null;
  selectedDocument.value = null;
  expandedChunkIds.value = new Set();
}

function toggleChunk(chunkId: string) {
  const next = new Set(expandedChunkIds.value);
  if (next.has(chunkId)) {
    next.delete(chunkId);
  } else {
    next.add(chunkId);
  }
  expandedChunkIds.value = next;
}

function previewText(value: string | null | undefined, maxLength = 180): string {
  const compact = (value ?? "").replace(/\s+/g, " ").trim();
  if (!compact) {
    return "暂无可预览内容";
  }
  return compact.length > maxLength ? `${compact.slice(0, maxLength).trim()}...` : compact;
}

function documentPreviewText(document: DocumentSummary | DocumentDetail): string {
  if (document.status === "processing") {
    return "文档正在解析，完成后会自动进入 RAG 检索。";
  }
  if (document.status === "failed") {
    return document.error_message || "文档解析失败";
  }
  return document.summary || previewText("raw_text" in document ? document.raw_text : "");
}

const visibleDocumentChunks = computed(() =>
  selectedDocument.value && selectedDocument.value.status === "ready"
    ? selectedDocument.value.chunks.slice(0, 10)
    : []
);

const uploadDisabled = computed(() => documentLoading.value || (isExpanded.value && loading.value));
const sidebarDocumentHint = computed(() => {
  if (documentLoading.value) {
    return "正在上传并解析...";
  }
  if (loading.value) {
    return "研究进行中暂不上传新文档；新增文档可在下一次研究前加入。";
  }
  return "可查看、删除文档；开始研究前上传的文档会参与本次 RAG 检索。";
});

async function handleDocumentUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) {
    return;
  }

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
    documents.value = [
      document,
      ...documents.value.filter((item) => item.id !== document.id)
    ];
    documentSuccess.value = `已上传 ${document.filename}，正在后台解析`;
    updateDocumentPolling();
    await selectDocument(document.id);
  } catch (err) {
    documentError.value = err instanceof Error ? err.message : "文档上传失败";
  } finally {
    documentLoading.value = false;
    input.value = "";
  }
}

function documentStatusLabel(document: DocumentSummary | DocumentDetail): string {
  if (document.status === "processing") {
    return "解析中";
  }
  if (document.status === "failed") {
    return "解析失败";
  }
  return "可检索";
}

function documentStatusText(document: DocumentSummary | DocumentDetail): string {
  return `${documentStatusLabel(document)} · ${document.chunk_count} 片段 · ${formatFileSize(document.size_bytes)}`;
}

function updateDocumentPolling() {
  const shouldPoll = documents.value.some((document) => document.status === "processing");
  if (shouldPoll && documentPollTimer === null) {
    documentPollTimer = window.setInterval(() => {
      void refreshDocuments();
    }, 2000);
  }
  if (!shouldPoll && documentPollTimer !== null) {
    window.clearInterval(documentPollTimer);
    documentPollTimer = null;
  }
}

function formatFileSize(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

const handleSubmit = async () => {
  if (!form.topic.trim()) {
    error.value = "请输入研究主题";
    return;
  }

  if (currentController) {
    currentController.abort();
    currentController = null;
  }

  researchDocumentCount.value = documents.value.length;
  loading.value = true;
  error.value = "";
  isExpanded.value = true;
  resetWorkflowState();

  const controller = new AbortController();
  currentController = controller;

  const payload = {
    topic: form.topic.trim(),
    search_api: form.searchApi || undefined
  };

  try {
    await runResearchStream(
      payload,
      (event: ResearchStreamEvent) => {
        if (event.type === "status") {
          const message =
            typeof event.message === "string" && event.message.trim()
              ? event.message
              : "流程状态更新";
          progressLogs.value.push(message);

          const payload = event as Record<string, unknown>;
          const task = findTask(payload.task_id);
          if (task && message) {
            task.notices.push(message);
            applyNoteMetadata(task, payload);
          }
          return;
        }

        if (event.type === "workflow_node") {
          const payload = event as Record<string, unknown>;
          upsertWorkflowNode(payload);
          const nodeId = extractOptionalString(payload.node_id);
          if (nodeId) {
            selectedWorkflowNodeId.value = nodeId;
          }
          const label = extractOptionalString(payload.label) ?? "工作流节点";
          const status = extractOptionalString(payload.status) ?? "";
          const detail = extractOptionalString(payload.detail);
          if (status === "in_progress") {
            progressLogs.value.push(`${label}开始`);
          } else if (detail) {
            progressLogs.value.push(`${label}：${detail}`);
          }
          return;
        }

        if (event.type === "workflow_graph") {
          applyWorkflowGraph(event as Record<string, unknown>);
          progressLogs.value.push("已加载 LangGraph 工作流拓扑");
          return;
        }

        if (event.type === "todo_list") {
          const tasks = Array.isArray(event.tasks)
            ? (event.tasks as Record<string, unknown>[])
            : [];

          todoTasks.value = tasks.map((item, index) => {
            const rawId =
              typeof item.id === "number"
                ? item.id
                : typeof item.id === "string"
                ? Number(item.id)
                : index + 1;
            const id = Number.isFinite(rawId) ? Number(rawId) : index + 1;
            const noteId =
              typeof item.note_id === "string" && item.note_id.trim()
                ? item.note_id.trim()
                : null;
            const notePath =
              typeof item.note_path === "string" && item.note_path.trim()
                ? item.note_path.trim()
                : null;

            return {
              id,
              title:
                typeof item.title === "string" && item.title.trim()
                  ? item.title.trim()
                  : `任务${id}`,
              intent:
                typeof item.intent === "string" && item.intent.trim()
                  ? item.intent.trim()
                  : "探索与主题相关的关键信息",
              query:
                typeof item.query === "string" && item.query.trim()
                  ? item.query.trim()
                  : form.topic.trim(),
              status:
                typeof item.status === "string" && item.status.trim()
                  ? item.status.trim()
                  : "pending",
              summary: "",
              sourcesSummary: "",
              sourceItems: [],
              notices: [],
              noteId,
              notePath,
              toolCalls: []
            } as TodoTaskView;
          });

          if (todoTasks.value.length) {
            activeTaskId.value = todoTasks.value[0].id;
            progressLogs.value.push("已生成任务清单");
          } else {
            progressLogs.value.push("未生成任务清单，使用默认任务继续");
          }
          return;
        }

        if (event.type === "task_status") {
          const payload = event as Record<string, unknown>;
          const task = findTask(event.task_id);
          if (!task) {
            return;
          }

          upsertTaskMetadata(task, payload);
          applyNoteMetadata(task, payload);
          const status =
            typeof event.status === "string" && event.status.trim()
              ? event.status.trim()
              : task.status;
          task.status = status;

          if (status === "in_progress") {
            task.summary = "";
            task.sourcesSummary = "";
            task.sourceItems = [];
            task.notices = [];
            activeTaskId.value = task.id;
            progressLogs.value.push(`开始执行任务：${task.title}`);
          } else if (status === "completed") {
            if (typeof event.summary === "string" && event.summary.trim()) {
              task.summary = event.summary.trim();
            }
            if (
              typeof event.sources_summary === "string" &&
              event.sources_summary.trim()
            ) {
              task.sourcesSummary = event.sources_summary.trim();
              task.sourceItems = parseSources(task.sourcesSummary);
            }
            progressLogs.value.push(`完成任务：${task.title}`);
            if (activeTaskId.value === task.id) {
              pulse(summaryHighlight);
              pulse(sourcesHighlight);
            }
          } else if (status === "skipped") {
            progressLogs.value.push(`任务跳过：${task.title}`);
          }
          return;
        }

        if (event.type === "sources") {
          const payload = event as Record<string, unknown>;
          const task = findTask(event.task_id);
          if (!task) {
            return;
          }

          const textCandidates = [
            payload.latest_sources,
            payload.sources_summary,
            payload.raw_context
          ];
          const latestText = textCandidates
            .map((value) => (typeof value === "string" ? value.trim() : ""))
            .find((value) => value);

          if (latestText) {
            task.sourcesSummary = latestText;
            task.sourceItems = parseSources(latestText);
            if (activeTaskId.value === task.id) {
              pulse(sourcesHighlight);
            }
            progressLogs.value.push(`已更新任务来源：${task.title}`);
          }

          if (typeof payload.backend === "string") {
            progressLogs.value.push(
              `当前使用搜索后端：${payload.backend}`
            );
          }

          applyNoteMetadata(task, payload);

          return;
        }

        if (event.type === "task_summary_chunk") {
          const payload = event as Record<string, unknown>;
          const task = findTask(event.task_id);
          if (!task) {
            return;
          }
          const chunk =
            typeof event.content === "string" ? event.content : "";
          task.summary += chunk;
          applyNoteMetadata(task, payload);
          if (activeTaskId.value === task.id) {
            pulse(summaryHighlight);
          }
          return;
        }

        if (event.type === "tool_call") {
          const payload = event as Record<string, unknown>;
          const eventId =
            typeof payload.event_id === "number"
              ? payload.event_id
              : Date.now();
          const agent =
            typeof payload.agent === "string" && payload.agent.trim()
              ? payload.agent.trim()
              : "Agent";
          const tool =
            typeof payload.tool === "string" && payload.tool.trim()
              ? payload.tool.trim()
              : "tool";
          const parameters = ensureRecord(payload.parameters);
          const result =
            typeof payload.result === "string" ? payload.result : "";
          const noteId = extractOptionalString(payload.note_id);
          const notePath = extractOptionalString(payload.note_path);

          const task = findTask(payload.task_id);
          if (task) {
            task.toolCalls.push({
              eventId,
              agent,
              tool,
              parameters,
              result,
              noteId,
              notePath,
              timestamp: Date.now()
            });
            if (noteId) {
              task.noteId = noteId;
            }
            if (notePath) {
              task.notePath = notePath;
            }
            const logSummary = noteId
              ? `${agent} 调用了 ${tool}（任务 ${task.id}，笔记 ${noteId}）`
              : `${agent} 调用了 ${tool}（任务 ${task.id}）`;
            progressLogs.value.push(logSummary);
            if (activeTaskId.value === task.id) {
              pulse(toolHighlight);
            }
          } else {
            progressLogs.value.push(`${agent} 调用了 ${tool}`);
          }
          return;
        }

        if (event.type === "final_report") {
          const report =
            typeof event.report === "string" && event.report.trim()
              ? event.report.trim()
              : "";
          reportMarkdown.value = report || "报告生成失败，未获得有效内容";
          pulse(reportHighlight);
          progressLogs.value.push("最终报告已生成");
          return;
        }

        if (event.type === "error") {
          const detail =
            typeof event.detail === "string" && event.detail.trim()
              ? event.detail
              : "研究过程中发生错误";
          error.value = detail;
          progressLogs.value.push("研究失败，已停止流程");
        }
      },
      { signal: controller.signal }
    );

    if (!reportMarkdown.value) {
      reportMarkdown.value = "暂无生成的报告";
    }
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      progressLogs.value.push("已取消当前研究任务");
    } else {
      error.value = err instanceof Error ? err.message : "请求失败";
    }
  } finally {
    loading.value = false;
    if (currentController === controller) {
      currentController = null;
    }
  }
};

const cancelResearch = () => {
  if (!loading.value || !currentController) {
    return;
  }
  progressLogs.value.push("正在尝试取消当前研究任务…");
  currentController.abort();
};

const goBack = () => {
  if (loading.value) {
    return; // 研究进行中不允许返回
  }
  isExpanded.value = false;
};

const startNewResearch = () => {
  if (loading.value) {
    cancelResearch();
  }
  resetWorkflowState();
  isExpanded.value = false;
  form.topic = "";
  form.searchApi = "";
};

onMounted(() => {
  void refreshDocuments();
});

onBeforeUnmount(() => {
  if (documentPollTimer !== null) {
    window.clearInterval(documentPollTimer);
    documentPollTimer = null;
  }
  if (currentController) {
    currentController.abort();
    currentController = null;
  }
});
</script>


<style scoped>
.app-shell {
  position: relative;
  min-height: 100vh;
  padding: 72px 24px;
  display: flex;
  justify-content: center;
  align-items: center;
  background: radial-gradient(circle at 20% 20%, #f8fafc, #dbeafe 60%);
  color: #1f2937;
  overflow: hidden;
  box-sizing: border-box;
  transition: padding 0.4s ease;
}

.app-shell.expanded {
  padding: 0;
  align-items: stretch;
}

.aurora {
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.55;
}

.aurora span {
  position: absolute;
  width: 45vw;
  height: 45vw;
  max-width: 520px;
  max-height: 520px;
  background: radial-gradient(circle, rgba(148, 197, 255, 0.35), transparent 60%);
  filter: blur(90px);
  animation: float 26s infinite linear;
}

.aurora span:nth-child(1) {
  top: -20%;
  left: -18%;
  animation-delay: 0s;
}

.aurora span:nth-child(2) {
  bottom: -25%;
  right: -20%;
  background: radial-gradient(circle, rgba(166, 139, 255, 0.28), transparent 60%);
  animation-delay: -9s;
}

.aurora span:nth-child(3) {
  top: 35%;
  left: 45%;
  background: radial-gradient(circle, rgba(164, 219, 216, 0.26), transparent 60%);
  animation-delay: -16s;
}

.layout {
  position: relative;
  width: 100%;
  display: flex;
  gap: 24px;
  z-index: 1;
  transition: all 0.4s ease;
}

.layout-centered {
  max-width: 600px;
  justify-content: center;
  align-items: center;
}

.layout-fullscreen {
  height: 100vh;
  max-width: 100%;
  gap: 0;
  align-items: stretch;
}

.panel {
  position: relative;
  flex: 1 1 360px;
  padding: 24px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: 0 24px 48px rgba(15, 23, 42, 0.12);
  backdrop-filter: blur(8px);
  overflow: hidden;
}

.panel-form {
  max-width: 420px;
}

.panel-centered {
  width: 100%;
  max-width: 600px;
  padding: 40px;
  box-shadow: 0 32px 64px rgba(15, 23, 42, 0.15);
  transform: scale(1);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.panel-centered:hover {
  transform: scale(1.02);
  box-shadow: 0 40px 80px rgba(15, 23, 42, 0.2);
}

.panel-result {
  min-width: 360px;
  flex: 2 1 420px;
}

.panel::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.12), rgba(125, 86, 255, 0.1));
  opacity: 0;
  transition: opacity 0.35s ease;
  z-index: 0;
}

.panel:hover::before {
  opacity: 1;
}

.panel > * {
  position: relative;
  z-index: 1;
}

.panel-form h1 {
  margin: 0;
  font-size: 26px;
  letter-spacing: 0.01em;
}

.panel-form p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
}

.panel-head {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.logo {
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
  border-radius: 16px;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  box-shadow: 0 12px 28px rgba(59, 130, 246, 0.4);
}

.logo svg {
  width: 28px;
  height: 28px;
  fill: #f8fafc;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.field span {
  font-weight: 600;
  color: #475569;
}

textarea,
input,
select {
  font-family: inherit;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(255, 255, 255, 0.92);
  color: #1f2937;
  font-size: 14px;
  transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
}

textarea:focus,
input:focus,
select:focus {
  outline: none;
  border-color: rgba(37, 99, 235, 0.65);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
  background: #ffffff;
}

.options {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.option {
  flex: 1;
  min-width: 140px;
}

.form-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.submit {
  align-self: flex-start;
  padding: 12px 24px;
  border-radius: 16px;
  border: none;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: #ffffff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s, opacity 0.2s;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  position: relative;
}

.submit-label {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.submit .spinner {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: rgba(255, 255, 255, 0.85);
  stroke-linecap: round;
  animation: spin 1s linear infinite;
}

.submit:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.submit:not(:disabled):hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 28px rgba(37, 99, 235, 0.28);
}

.secondary-btn {
  padding: 10px 18px;
  border-radius: 14px;
  background: rgba(148, 163, 184, 0.12);
  border: 1px solid rgba(148, 163, 184, 0.28);
  color: #1f2937;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease;
}

.secondary-btn:hover {
  background: rgba(148, 163, 184, 0.2);
  border-color: rgba(148, 163, 184, 0.35);
  color: #0f172a;
}

.error-chip {
  margin-top: 16px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: rgba(248, 113, 113, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.35);
  border-radius: 14px;
  color: #b91c1c;
  font-size: 14px;
}

.error-chip svg {
  width: 18px;
  height: 18px;
  fill: currentColor;
}

.panel-result {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.status-main {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.status-controls {
  display: flex;
  gap: 8px;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(191, 219, 254, 0.28);
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 13px;
  color: #1f2937;
  border: 1px solid rgba(59, 130, 246, 0.35);
  transition: background 0.3s ease, color 0.3s ease;
}

.status-chip.active {
  background: rgba(129, 140, 248, 0.2);
  border-color: rgba(129, 140, 248, 0.4);
  color: #1e293b;
}

.status-chip .dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #2563eb;
  box-shadow: 0 0 12px rgba(37, 99, 235, 0.45);
  animation: pulse 1.8s ease-in-out infinite;
}

.status-meta {
  color: #64748b;
  font-size: 13px;
}

.timeline-wrapper {
  margin-top: 12px;
  max-height: 220px;
  overflow-y: auto;
  padding-right: 8px;
  scrollbar-width: thin;
  scrollbar-color: rgba(129, 140, 248, 0.45) rgba(226, 232, 240, 0.6);
}

.timeline-wrapper::-webkit-scrollbar {
  width: 6px;
}

.timeline-wrapper::-webkit-scrollbar-track {
  background: rgba(226, 232, 240, 0.6);
  border-radius: 999px;
}

.timeline-wrapper::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, rgba(129, 140, 248, 0.8), rgba(59, 130, 246, 0.7));
  border-radius: 999px;
}

.timeline-wrapper::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(180deg, rgba(99, 102, 241, 0.9), rgba(37, 99, 235, 0.8));
}

.timeline {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
  position: relative;
  padding-left: 12px;
}

.timeline::before {
  content: "";
  position: absolute;
  top: 8px;
  bottom: 8px;
  left: 0;
  width: 2px;
  background: linear-gradient(180deg, rgba(59, 130, 246, 0.35), rgba(129, 140, 248, 0.15));
}

.timeline li {
  position: relative;
  padding-left: 24px;
  color: #1e293b;
  font-size: 14px;
  line-height: 1.5;
}

.timeline-node {
  position: absolute;
  left: -12px;
  top: 6px;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: linear-gradient(135deg, #38bdf8, #7c3aed);
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.22);
}

.timeline-enter-active,
.timeline-leave-active {
  transition: all 0.35s ease, opacity 0.35s ease;
}

.timeline-enter-from,
.timeline-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.result-workbench {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(340px, 420px);
  gap: 20px;
  align-items: start;
}

.workflow-panel,
.content-column,
.evidence-column {
  min-width: 0;
}

.content-column,
.evidence-column {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.workflow-panel {
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(148, 163, 184, 0.26);
  border-radius: 12px;
  padding: 18px;
  box-shadow: inset 0 0 0 1px rgba(226, 232, 240, 0.4);
}

.evidence-column {
  position: sticky;
  top: 0;
}

.workflow-panel-header h3 {
  margin: 0;
  font-size: 16px;
  color: #1f2937;
}

.workflow-panel-header p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
}

.workflow-map {
  margin-top: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow-x: auto;
  padding-bottom: 4px;
}

.workflow-global-row,
.workflow-lane-nodes {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(150px, 1fr);
  gap: 12px;
  align-items: stretch;
  min-width: 560px;
}

.workflow-global-row {
  padding: 10px;
  border-radius: 10px;
  background: rgba(239, 246, 255, 0.72);
  border: 1px solid rgba(147, 197, 253, 0.32);
}

.report-row {
  background: rgba(240, 253, 244, 0.72);
  border-color: rgba(134, 239, 172, 0.34);
}

.workflow-lanes {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 760px;
}

.workflow-lane {
  display: grid;
  grid-template-columns: 170px 1fr;
  gap: 12px;
  align-items: stretch;
}

.workflow-lane-label,
.graph-node {
  border: 1px solid rgba(148, 163, 184, 0.24);
  background: rgba(255, 255, 255, 0.88);
  color: #1f2937;
  text-align: left;
  cursor: pointer;
}

.workflow-lane-label {
  border-radius: 10px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 5px;
  justify-content: center;
  min-height: 82px;
}

.workflow-lane-label span {
  color: #64748b;
  font-size: 12px;
}

.workflow-lane-label strong {
  font-size: 13px;
  line-height: 1.45;
}

.graph-node {
  position: relative;
  min-height: 82px;
  border-radius: 10px;
  padding: 12px 12px 12px 34px;
  display: flex;
  flex-direction: column;
  gap: 5px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.graph-node::after {
  content: "";
  position: absolute;
  top: 50%;
  right: -12px;
  width: 12px;
  height: 1px;
  background: rgba(100, 116, 139, 0.28);
}

.graph-node:last-child::after {
  display: none;
}

.graph-node-dot {
  position: absolute;
  top: 15px;
  left: 13px;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #94a3b8;
}

.graph-node strong {
  font-size: 13px;
  line-height: 1.35;
}

.graph-node small {
  color: #64748b;
  font-size: 11px;
  line-height: 1.45;
}

.graph-node.in_progress {
  background: rgba(224, 231, 255, 0.62);
  border-color: rgba(99, 102, 241, 0.36);
}

.graph-node.in_progress .graph-node-dot {
  background: #6366f1;
  box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.16);
}

.graph-node.completed {
  background: rgba(220, 252, 231, 0.62);
  border-color: rgba(34, 197, 94, 0.28);
}

.graph-node.completed .graph-node-dot {
  background: #22c55e;
}

.graph-node.skipped {
  background: rgba(241, 245, 249, 0.72);
}

.graph-node.skipped .graph-node-dot {
  background: #64748b;
}

.graph-node.failed {
  background: rgba(254, 226, 226, 0.72);
  border-color: rgba(239, 68, 68, 0.35);
}

.graph-node.failed .graph-node-dot {
  background: #ef4444;
}

.graph-node.selected {
  border-color: rgba(59, 130, 246, 0.72);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.14);
}

.tasks-section {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 20px;
  align-items: start;
}

@media (max-width: 960px) {
  .result-workbench {
    grid-template-columns: 1fr;
  }

  .evidence-column {
    position: relative;
  }

  .tasks-section {
    grid-template-columns: 1fr;
  }
}

.tasks-list {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.26);
  border-radius: 18px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  box-shadow: inset 0 0 0 1px rgba(226, 232, 240, 0.4);
}

.tasks-list h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.tasks-list ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-item {
  border-radius: 14px;
  border: 1px solid transparent;
  transition: border-color 0.2s ease, background 0.2s ease;
}

.task-item.completed {
  border-color: rgba(56, 189, 248, 0.35);
  background: rgba(191, 219, 254, 0.28);
}

.task-item.active {
  border-color: rgba(129, 140, 248, 0.5);
  background: rgba(224, 231, 255, 0.5);
}

.task-button {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px 6px;
  background: transparent;
  border: none;
  color: inherit;
  cursor: pointer;
  text-align: left;
}

.task-title {
  font-weight: 600;
  font-size: 14px;
  color: #1e293b;
}

.task-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  color: #1f2937;
  background: rgba(148, 163, 184, 0.2);
}

.task-status.pending {
  background: rgba(148, 163, 184, 0.18);
  color: #475569;
}

.task-status.in_progress {
  background: rgba(129, 140, 248, 0.24);
  color: #312e81;
}

.task-status.completed {
  background: rgba(34, 197, 94, 0.2);
  color: #15803d;
}

.task-status.skipped {
  background: rgba(248, 113, 113, 0.18);
  color: #b91c1c;
}

.task-intent {
  margin: 0;
  padding: 0 14px 12px 14px;
  font-size: 13px;
  color: #64748b;
}

.task-detail {
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(148, 163, 184, 0.26);
  border-radius: 18px;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  box-shadow: inset 0 0 0 1px rgba(226, 232, 240, 0.5);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 12px;
}

.task-chip-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.task-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
}

.task-header .muted {
  margin: 6px 0 0;
}

.task-label {
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(191, 219, 254, 0.32);
  border: 1px solid rgba(59, 130, 246, 0.35);
  font-size: 12px;
  color: #1e3a8a;
}

.task-label.note-chip {
  background: rgba(34, 197, 94, 0.2);
  border-color: rgba(34, 197, 94, 0.35);
  color: #15803d;
}

.task-label.path-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 360px;
  background: rgba(56, 189, 248, 0.2);
  border-color: rgba(56, 189, 248, 0.35);
  color: #0369a1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.path-label {
  font-weight: 500;
}

.path-text {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chip-action {
  border: none;
  background: rgba(56, 189, 248, 0.2);
  color: #0369a1;
  padding: 3px 8px;
  border-radius: 10px;
  font-size: 11px;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease;
}

.chip-action:hover {
  background: rgba(14, 165, 233, 0.28);
  color: #0f172a;
}

.task-notices {
  background: rgba(191, 219, 254, 0.28);
  border: 1px solid rgba(96, 165, 250, 0.35);
  border-radius: 16px;
  padding: 14px 18px;
  color: #1f2937;
}

.task-notices h4 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
}

.task-notices ul {
  list-style: disc;
  margin: 0 0 0 18px;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.task-notices li {
  font-size: 13px;
}

.report-block {
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(148, 163, 184, 0.26);
  border-radius: 18px;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.report-block h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
}

.report-block-main .block-pre {
  max-height: 560px;
}

.block-pre {
  font-family: "JetBrains Mono", "Fira Code", ui-monospace, SFMono-Regular,
    Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  color: #1f2937;
  background: rgba(248, 250, 252, 0.9);
  padding: 16px;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  overflow: auto;
  max-height: 420px;
  scrollbar-width: thin;
  scrollbar-color: rgba(129, 140, 248, 0.6) rgba(226, 232, 240, 0.7);
}

.block-pre::-webkit-scrollbar {
  width: 6px;
}

.block-pre::-webkit-scrollbar-track {
  background: rgba(226, 232, 240, 0.7);
  border-radius: 999px;
}

.block-pre::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, rgba(99, 102, 241, 0.75), rgba(59, 130, 246, 0.65));
  border-radius: 999px;
}

.block-pre::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(180deg, rgba(79, 70, 229, 0.8), rgba(37, 99, 235, 0.75));
}

.summary-block .block-pre,
.sources-block .block-pre {
  max-height: 360px;
}


.tools-block {
  position: relative;
  margin-top: 16px;
  padding: 20px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: inset 0 0 0 1px rgba(226, 232, 240, 0.4);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tools-block h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  letter-spacing: 0.02em;
}

.tool-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tool-entry {
  background: rgba(248, 250, 252, 0.95);
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 14px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tool-entry-header {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
}

.tool-entry-title {
  font-weight: 600;
  color: #1f2937;
}

.tool-entry-note {
  font-size: 12px;
  color: #0f766e;
}

.tool-entry-path {
  margin: 0;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  color: #2563eb;
}

.tool-subtitle {
  margin: 0;
  font-size: 13px;
  color: #475569;
  font-weight: 500;
}

.tool-pre {
  font-family: "JetBrains Mono", "Fira Code", ui-monospace, SFMono-Regular,
    Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: #1f2937;
  background: rgba(248, 250, 252, 0.9);
  padding: 12px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  overflow: auto;
  max-height: 260px;
  scrollbar-width: thin;
  scrollbar-color: rgba(129, 140, 248, 0.6) rgba(226, 232, 240, 0.7);
}

.tool-pre::-webkit-scrollbar {
  width: 6px;
}

.tool-pre::-webkit-scrollbar-track {
  background: rgba(226, 232, 240, 0.7);
}

.tool-pre::-webkit-scrollbar-thumb {
  background: rgba(99, 102, 241, 0.7);
  border-radius: 10px;
}

.link-btn {
  background: none;
  border: none;
  color: #0369a1;
  cursor: pointer;
  padding: 0 4px;
  font-size: 12px;
  border-radius: 8px;
  transition: color 0.2s ease, background 0.2s ease;
}

.link-btn:hover {
  color: #0ea5e9;
  background: rgba(14, 165, 233, 0.16);
}


.sources-block,
.summary-block {
  position: relative;
  margin-top: 16px;
  padding: 18px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: inset 0 0 0 1px rgba(226, 232, 240, 0.4);
}

.sources-history {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sources-history h4 {
  margin: 0;
  color: #1f2937;
  font-size: 14px;
  letter-spacing: 0.01em;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.history-list details {
  background: rgba(248, 250, 252, 0.95);
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 14px;
  padding: 12px 16px;
  color: #1f2937;
  transition: border-color 0.2s ease, background 0.2s ease;
}

.history-list details[open] {
  background: rgba(224, 231, 255, 0.55);
  border-color: rgba(129, 140, 248, 0.4);
}

.history-list summary {
  cursor: pointer;
  font-weight: 600;
  outline: none;
  list-style: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.history-list summary::-webkit-details-marker {
  display: none;
}

.history-list summary::after {
  content: "▾";
  margin-left: 6px;
  font-size: 12px;
  opacity: 0.7;
  transition: transform 0.2s ease;
}

.history-list details[open] summary::after {
  transform: rotate(180deg);
}

.block-highlight {
  animation: glow 1.2s ease;
}

.sources-block h3,
.summary-block h3 {
  margin: 0 0 14px;
  color: #1f2937;
  letter-spacing: 0.02em;
}

.sources-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.source-item {
  position: relative;
  display: inline-flex;
  flex-direction: column;
  gap: 6px;
}

.source-link {
  color: #2563eb;
  text-decoration: none;
  font-weight: 600;
  letter-spacing: 0.01em;
  transition: color 0.2s ease;
}

.source-link::after {
  content: " ↗";
  font-size: 12px;
  opacity: 0.6;
}

.source-link:hover {
  color: #0f172a;
}

.source-tooltip {
  display: none;
  position: absolute;
  bottom: calc(100% + 12px);
  left: 50%;
  transform: translateX(-50%);
  background: rgba(255, 255, 255, 0.98);
  color: #1f2937;
  padding: 14px 16px;
  border-radius: 16px;
  box-shadow: 0 18px 32px rgba(15, 23, 42, 0.18);
  width: min(420px, 90vw);
  z-index: 20;
  border: 1px solid rgba(148, 163, 184, 0.24);
}

.source-tooltip::after {
  content: "";
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border-width: 10px;
  border-style: solid;
  border-color: rgba(255, 255, 255, 0.98) transparent transparent transparent;
}

.source-tooltip::before {
  content: "";
  position: absolute;
  bottom: -12px;
  left: 50%;
  transform: translateX(-50%);
  border-width: 12px 10px 0 10px;
  border-style: solid;
  border-color: rgba(255, 255, 255, 0.98) transparent transparent transparent;
  filter: drop-shadow(0 -2px 4px rgba(15, 23, 42, 0.12));
}

.source-tooltip p {
  margin: 0 0 8px;
  font-size: 13px;
  line-height: 1.6;
}

.source-tooltip p:last-child {
  margin-bottom: 0;
}

.muted-text {
  color: #64748b;
}

.source-item:hover .source-tooltip,
.source-item:focus-within .source-tooltip {
  display: block;
}

.hint.muted {
  color: #64748b;
}

@keyframes float {
  0% {
    transform: translate3d(0, 0, 0) rotate(0deg);
  }
  50% {
    transform: translate3d(10%, 6%, 0) rotate(3deg);
  }
  100% {
    transform: translate3d(0, 0, 0) rotate(0deg);
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.3);
    opacity: 0.5;
  }
}

@keyframes glow {
  0% {
    box-shadow: 0 0 0 rgba(59, 130, 246, 0.3);
    border-color: rgba(59, 130, 246, 0.5);
  }
  100% {
    box-shadow: inset 0 0 0 1px rgba(59, 130, 246, 0.12);
    border-color: rgba(148, 163, 184, 0.2);
  }
}

@media (max-width: 960px) {
  .app-shell {
    padding: 56px 16px;
  }

  .layout {
    flex-direction: column;
    align-items: stretch;
  }

  .panel {
    padding: 22px;
  }

  .panel-form,
  .panel-result {
    max-width: none;
  }

  .status-bar {
    flex-direction: column;
    align-items: flex-start;
  }

  .status-main,
  .status-controls {
    width: 100%;
  }

  .status-controls {
    justify-content: flex-start;
  }
}

@media (max-width: 600px) {
  .options {
    flex-direction: column;
  }

  .status-meta {
    font-size: 12px;
  }

  .panel-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .panel-form h1 {
    font-size: 24px;
  }
}

/* 侧边栏样式 */
.sidebar {
  width: 400px;
  min-width: 400px;
  height: 100vh;
  background: rgba(255, 255, 255, 0.98);
  border-right: 1px solid rgba(148, 163, 184, 0.2);
  padding: 32px 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  overflow-y: auto;
  box-shadow: 4px 0 24px rgba(15, 23, 42, 0.08);
}

.sidebar-header {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sidebar-header h2 {
  font-size: 24px;
  font-weight: 700;
  margin: 0;
  color: #1f2937;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 12px;
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  width: fit-content;
}

.back-btn:hover:not(:disabled) {
  background: rgba(59, 130, 246, 0.1);
  border-color: #3b82f6;
  color: #3b82f6;
}

.back-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.research-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item label {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #64748b;
}

.info-item p {
  margin: 0;
  font-size: 14px;
  color: #1f2937;
  line-height: 1.6;
}

.topic-display {
  font-size: 16px !important;
  font-weight: 600;
  color: #0f172a !important;
  padding: 12px;
  background: rgba(59, 130, 246, 0.05);
  border-radius: 8px;
  border-left: 3px solid #3b82f6;
}

.progress-bar {
  width: 100%;
  height: 8px;
  background: rgba(148, 163, 184, 0.2);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #8b5cf6);
  border-radius: 4px;
  transition: width 0.5s ease;
}

.progress-text {
  font-size: 13px !important;
  color: #64748b !important;
  font-weight: 500;
}

.node-detail-block {
  padding: 18px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: inset 0 0 0 1px rgba(226, 232, 240, 0.4);
}

.node-detail-block h3 {
  margin: 0 0 10px;
  font-size: 16px;
  color: #1f2937;
}

.node-detail-title {
  margin: 0 0 8px;
  color: #0f172a;
  font-weight: 600;
}

.document-library {
  margin-top: 4px;
}

.home-document-library {
  margin-top: 4px;
  padding: 14px;
  border-radius: 16px;
  background: rgba(248, 250, 252, 0.72);
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.document-library-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.document-library-head label {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #64748b;
}

.document-library-head span {
  color: #2563eb;
  font-size: 12px;
  font-weight: 600;
}

.document-dropzone {
  border: 1px dashed rgba(59, 130, 246, 0.35);
  border-radius: 14px;
  padding: 14px;
  background: rgba(239, 246, 255, 0.72);
  color: #1f2937;
}

.document-dropzone strong {
  display: block;
  font-size: 14px;
  margin-bottom: 6px;
}

.document-dropzone p {
  font-size: 12px !important;
  color: #64748b !important;
  line-height: 1.5;
}

.document-dropzone.muted {
  border-color: rgba(148, 163, 184, 0.32);
  background: rgba(241, 245, 249, 0.74);
}

.upload-button {
  margin-top: 10px;
  width: 100%;
  border: none;
  border-radius: 12px;
  padding: 10px 12px;
  background: linear-gradient(135deg, #2563eb, #0f766e);
  color: #ffffff;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  box-sizing: border-box;
}

.upload-button input {
  display: none;
}

.upload-button.disabled {
  opacity: 0.62;
  cursor: wait;
}

.document-message {
  margin: 0;
  padding: 8px 10px;
  border-radius: 10px;
  font-size: 12px !important;
  line-height: 1.45 !important;
}

.document-message.success {
  background: rgba(220, 252, 231, 0.78);
  color: #166534 !important;
}

.document-message.error {
  background: rgba(254, 226, 226, 0.78);
  color: #991b1b !important;
}

.document-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.document-list li {
  display: flex;
}

.document-empty {
  margin: 0;
  color: #64748b !important;
  font-size: 12px !important;
}

.document-item-button {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(148, 163, 184, 0.22);
  cursor: pointer;
  text-align: left;
  transition: background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.document-item-button:hover,
.document-item-button.active {
  background: rgba(219, 234, 254, 0.72);
  border-color: rgba(59, 130, 246, 0.36);
}

.document-item-button.active {
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

.document-name {
  max-width: 100%;
  color: #0f172a;
  font-size: 13px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.document-meta {
  color: #64748b;
  font-size: 12px;
}

.document-detail-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border-radius: 12px;
  background: rgba(248, 250, 252, 0.86);
  border: 1px solid rgba(148, 163, 184, 0.24);
}

.document-detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.document-detail-header div {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.document-detail-header strong {
  color: #0f172a;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.document-detail-header span {
  color: #64748b;
  font-size: 12px;
}

.document-delete-btn {
  flex: 0 0 auto;
  border: 1px solid rgba(239, 68, 68, 0.24);
  border-radius: 10px;
  padding: 6px 9px;
  background: rgba(254, 226, 226, 0.72);
  color: #991b1b;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
}

.document-delete-btn:disabled {
  opacity: 0.62;
  cursor: wait;
}

.document-preview {
  margin: 0;
  padding: 9px 10px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.72);
  color: #334155 !important;
  font-size: 12px !important;
  line-height: 1.55 !important;
  word-break: break-word;
}

.document-chunks {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.document-chunk {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 10px;
  padding: 9px 10px;
  background: rgba(255, 255, 255, 0.78);
  text-align: left;
  cursor: pointer;
}

.document-chunk span {
  display: block;
  margin-bottom: 4px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 600;
}

.document-chunk p {
  margin: 0;
  color: #334155 !important;
  font-size: 12px !important;
  line-height: 1.55 !important;
  white-space: pre-wrap;
  word-break: break-word;
}
.sidebar-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 16px;
  border-top: 1px solid rgba(148, 163, 184, 0.2);
}

.new-research-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px 20px;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  border: none;
  border-radius: 12px;
  color: white;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

.new-research-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(59, 130, 246, 0.4);
}

.new-research-btn:active {
  transform: translateY(0);
}

/* 全屏状态下的结果面板 */
.layout-fullscreen .panel-result {
  flex: 1;
  height: 100vh;
  border-radius: 0;
  border: none;
  overflow-y: auto;
  max-width: none;
}

@media (max-width: 1024px) {
  .sidebar {
    width: 320px;
    min-width: 320px;
  }
}

@media (max-width: 768px) {
  .layout-fullscreen {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
    min-width: 100%;
    height: auto;
    max-height: 40vh;
  }

  .layout-fullscreen .panel-result {
    height: 60vh;
  }
}
</style>
