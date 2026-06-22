<template>
  <main class="app-shell" :class="{ expanded: isExpanded }">
    <div class="aurora" aria-hidden="true">
      <span></span>
      <span></span>
      <span></span>
    </div>

    <div v-if="!isExpanded" class="layout layout-centered">
      <ResearchForm
        :topic="form.topic"
        :search-api="form.searchApi"
        :search-menu-open="searchMenuOpen"
        :selected-search-label="selectedSearchLabel"
        :search-option-items="searchOptionItems"
        :loading="loading"
        :error="error"
        @update:topic="form.topic = $event"
        @update:search-api="form.searchApi = $event"
        @update:search-menu-open="searchMenuOpen = $event"
        @submit="handleSubmit"
        @cancel="cancelResearch"
      >
        <template #documents>
          <DocumentLibrary
            variant="home"
            :header-text="documents.length ? `${documents.length} 个文档可检索` : '未上传文档'"
            :dropzone-title="documents.length ? '研究将优先检索这些文档' : '先上传研究文档'"
            :dropzone-hint="documentLoading ? '正在上传并解析...' : '支持 .txt / .md / .pdf / .docx，上传后会后台解析并进入 RAG 检索。'"
            empty-text="暂无文档，仍可直接开始研究。"
            :documents="documents"
            :document-loading="documentLoading"
            :document-detail-loading="documentDetailLoading"
            :document-deleting="documentDeleting"
            :document-retrying="documentRetrying"
            :upload-disabled="uploadDisabled"
            :document-success="documentSuccess"
            :document-error="documentError"
            :selected-document-id="selectedDocumentId"
            :selected-document="selectedDocument"
            :visible-document-chunks="visibleDocumentChunks"
            :expanded-chunk-ids="expandedChunkIds"
            :document-status-text="documentStatusText"
            :document-preview-text="documentPreviewText"
            :preview-text="previewText"
            @upload="handleDocumentUpload"
            @select="selectDocument"
            @retry="handleRetryDocument"
            @delete="handleDeleteDocument"
            @toggle-chunk="toggleChunk"
          />
        </template>
      </ResearchForm>
    </div>

    <div v-else class="layout layout-fullscreen">
      <aside class="sidebar">
        <div class="sidebar-header">
          <button class="back-btn" @click="goBack" :disabled="loading">
            <svg viewBox="0 0 24 24" width="20" height="20">
              <path d="M19 12H5M12 19l-7-7 7-7" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            返回
          </button>
          <h2>深度研究助手</h2>
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
            <DocumentLibrary
              variant="sidebar"
              :header-text="`本次启动时 ${researchDocumentCount} 个文档可检索`"
              :dropzone-title="documents.length ? `${documents.length} 个文档在库` : '暂无文档'"
              :dropzone-hint="sidebarDocumentHint"
              empty-text="暂无文档"
              :muted="loading"
              :documents="documents"
              :document-loading="documentLoading"
              :document-detail-loading="documentDetailLoading"
              :document-deleting="documentDeleting"
              :document-retrying="documentRetrying"
              :upload-disabled="uploadDisabled"
              :document-success="documentSuccess"
              :document-error="documentError"
              :selected-document-id="selectedDocumentId"
              :selected-document="selectedDocument"
              :visible-document-chunks="visibleDocumentChunks"
              :expanded-chunk-ids="expandedChunkIds"
              :document-status-text="documentStatusText"
              :document-preview-text="documentPreviewText"
              :preview-text="previewText"
              @upload="handleDocumentUpload"
              @select="selectDocument"
              @retry="handleRetryDocument"
              @delete="handleDeleteDocument"
              @toggle-chunk="toggleChunk"
            />
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

      <section class="panel panel-result">
        <header class="status-bar">
          <div class="status-main">
            <div class="status-chip" :class="{ active: loading }">
              <span class="dot"></span>
              {{ loading ? "研究进行中" : "研究流程完成" }}
            </div>
            <span class="status-meta">
              任务进度：{{ completedTasks }} / {{ totalTasks || todoTasks.length || 1 }}
            </span>
          </div>
        </header>

        <div class="result-workbench">
          <div class="content-column">
            <WorkflowPanel
              :collapsed="workflowCollapsed"
              :completed-workflow-nodes="completedWorkflowNodes"
              :visible-workflow-nodes="visibleWorkflowNodes"
              :workflow-edges="workflowEdges"
              :global-workflow-nodes="globalWorkflowNodes"
              :task-workflow-rows="taskWorkflowRows"
              :report-workflow-nodes="reportWorkflowNodes"
              :selected-workflow-node-id="selectedWorkflowNodeId"
              :format-workflow-status="formatWorkflowStatus"
              @update:collapsed="workflowCollapsed = $event"
              @select-node="selectedWorkflowNodeId = $event"
              @select-task="activeTaskId = $event"
            />

            <TaskSection
              :todo-tasks="todoTasks"
              :active-task-id="activeTaskId"
              :current-task="currentTask"
              :current-task-title="currentTaskTitle"
              :current-task-intent="currentTaskIntent"
              :current-task-query="currentTaskQuery"
              :current-task-note-id="currentTaskNoteId"
              :current-task-note-path="currentTaskNotePath"
              :current-task-summary="currentTaskSummary"
              :summary-highlight="summaryHighlight"
              :format-task-status="formatTaskStatus"
              @update:active-task-id="activeTaskId = $event"
              @copy-note-path="copyNotePath"
            />

            <ReportBlock
              :report-markdown="reportMarkdown"
              :rendered-report-html="renderedReportHtml"
              :report-highlight="reportHighlight"
            />
          </div>

          <EvidenceColumn
            :selected-workflow-node="selectedWorkflowNode"
            :current-task-sources="currentTaskSources"
            :current-task-tool-calls="currentTaskToolCalls"
            :sources-highlight="sourcesHighlight"
            :tool-highlight="toolHighlight"
            :format-workflow-status="formatWorkflowStatus"
            :workflow-task-title="workflowTaskTitle"
            :is-document-source="isDocumentSource"
            :format-tool-parameters="formatToolParameters"
            :format-tool-result="formatToolResult"
            @copy-note-path="copyNotePath"
          />
        </div>
      </section>
    </div>
  </main>
</template>

<script lang="ts" setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";

import DocumentLibrary from "./components/DocumentLibrary.vue";
import EvidenceColumn from "./components/EvidenceColumn.vue";
import ReportBlock from "./components/ReportBlock.vue";
import ResearchForm from "./components/ResearchForm.vue";
import TaskSection from "./components/TaskSection.vue";
import WorkflowPanel from "./components/WorkflowPanel.vue";

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
import type { SourceItem, TodoTaskView, ToolCallLog, WorkflowEdgeView, WorkflowNodeView } from "./types";

const form = reactive({
  topic: "",
  searchApi: ""
});

const loading = ref(false);
const error = ref("");
const progressLogs = ref<string[]>([]);
const workflowCollapsed = ref(false);
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
const searchMenuOpen = ref(false);
const documentError = ref("");
const documentSuccess = ref("");
const researchDocumentCount = ref(0);
const selectedDocumentId = ref<string | null>(null);
const selectedDocument = ref<DocumentDetail | null>(null);
const expandedChunkIds = ref<Set<string>>(new Set());

let currentController: AbortController | null = null;
let documentPollTimer: number | null = null;

const searchOptionItems = [
  {
    value: "",
    label: "沿用后端配置",
    detail: "使用后端 .env 中的默认搜索引擎配置。"
  },
  {
    value: "advanced",
    label: "advanced",
    detail: "混合多个搜索引擎，返回结构化 JSON；适合需要全面结果的研究。"
  },
  {
    value: "duckduckgo",
    label: "duckduckgo",
    detail: "无需 API 密钥，免费且无需注册；适合快速体验。"
  },
  {
    value: "tavily",
    label: "tavily",
    detail: "需要 API 密钥，专为 AI 检索设计，结构化 JSON 质量高；适合生产环境。"
  },
  {
    value: "perplexity",
    label: "perplexity",
    detail: "需要 API 密钥，返回 AI 总结和来源；适合需要总结的场景。"
  },
  {
    value: "searxng",
    label: "searxng",
    detail: "自建后无需 API 密钥，开源可控；适合私有部署。"
  }
];

const selectedSearchLabel = computed(() =>
  searchOptionItems.find((item) => item.value === form.searchApi)?.label ?? "沿用后端配置"
);

function selectSearchApi(value: string) {
  form.searchApi = value;
  searchMenuOpen.value = false;
}

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
const renderedReportHtml = computed(() => renderMarkdown(reportMarkdown.value));

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderInlineMarkdown(value: string): string {
  return value
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\[([^\]]+)\]\(((?:https?:\/\/|document:\/\/)[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
}

function renderMarkdown(markdown: string): string {
  const lines = escapeHtml(markdown || "").split("\n");
  const html: string[] = [];
  let inList = false;
  let inCode = false;
  let codeLines: string[] = [];

  const closeList = () => {
    if (inList) {
      html.push("</ul>");
      inList = false;
    }
  };

  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      closeList();
      if (inCode) {
        html.push(`<pre><code>${codeLines.join("\n")}</code></pre>`);
        codeLines = [];
      }
      inCode = !inCode;
      continue;
    }

    if (inCode) {
      codeLines.push(line);
      continue;
    }

    const trimmed = line.trim();
    if (!trimmed) {
      closeList();
      continue;
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(trimmed);
    if (heading) {
      closeList();
      html.push(`<h${heading[1].length}>${renderInlineMarkdown(heading[2])}</h${heading[1].length}>`);
      continue;
    }

    const bullet = /^[-*]\s+(.+)$/.exec(trimmed);
    if (bullet) {
      if (!inList) {
        html.push("<ul>");
        inList = true;
      }
      html.push(`<li>${renderInlineMarkdown(bullet[1])}</li>`);
      continue;
    }

    closeList();
    html.push(`<p>${renderInlineMarkdown(trimmed)}</p>`);
  }

  closeList();
  if (inCode) {
    html.push(`<pre><code>${codeLines.join("\n")}</code></pre>`);
  }
  return html.join("");
}

function isDocumentSource(item: SourceItem): boolean {
  return item.url.startsWith("document://") || item.raw.includes("document://") || item.title.includes("document://");
}

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
  workflowCollapsed.value = false;
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


<style>
.app-shell {
  --bg: #f7f8fb;
  --surface: #ffffff;
  --surface-soft: #f9fafb;
  --surface-muted: #f1f5f9;
  --border: #e2e8f0;
  --border-strong: #cbd5e1;
  --text: #111827;
  --muted: #64748b;
  --subtle: #94a3b8;
  --primary: #2563eb;
  --primary-strong: #1d4ed8;
  --primary-soft: #eff6ff;
  --success: #16a34a;
  --success-soft: #ecfdf5;
  --warning: #ca8a04;
  --warning-soft: #fffbeb;
  --danger: #dc2626;
  --danger-soft: #fef2f2;
  --shadow: 0 16px 40px rgba(15, 23, 42, 0.08);

  position: relative;
  min-height: 100vh;
  padding: 64px 24px;
  display: flex;
  justify-content: center;
  align-items: center;
  background: var(--bg);
  color: var(--text);
  overflow: hidden;
  box-sizing: border-box;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.app-shell.expanded {
  padding: 0;
  align-items: stretch;
  overflow: hidden;
}

.aurora {
  display: none;
}

.layout {
  position: relative;
  z-index: 1;
  width: 100%;
  display: flex;
  gap: 24px;
}

.layout-centered {
  max-width: 640px;
  justify-content: center;
  align-items: center;
}

.layout-fullscreen {
  height: 100vh;
  max-width: 100%;
  gap: 0;
  align-items: stretch;
  background: var(--bg);
}

.panel {
  position: relative;
  flex: 1 1 360px;
  padding: 24px;
  border-radius: 18px;
  background: var(--surface);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
  overflow: hidden;
}

.panel-form {
  max-width: 440px;
}

.panel-centered {
  width: 100%;
  max-width: 640px;
  padding: 40px;
}

.panel-result {
  min-width: 360px;
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.layout-fullscreen .panel-result {
  height: 100vh;
  max-width: none;
  border: 0;
  border-radius: 0;
  box-shadow: none;
  overflow-y: auto;
}

.panel-head {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 28px;
}

.logo {
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
  border-radius: 14px;
  background: var(--primary);
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.18);
  flex: 0 0 auto;
}

.logo svg {
  width: 27px;
  height: 27px;
  fill: #ffffff;
}

.panel-form h1,
.sidebar-header h2,
.workflow-panel-header h3,
.tasks-list h3,
.task-header h3,
.report-block h3,
.sources-block h3,
.tools-block h3,
.node-detail-block h3,
.summary-block h3 {
  margin: 0;
  color: var(--text);
  letter-spacing: 0;
}

.panel-form h1 {
  font-size: 28px;
  line-height: 1.15;
  font-weight: 750;
}

.panel-form p {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.6;
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

.field span,
.info-item label,
.document-library-head label,
.tool-subtitle {
  font-size: 13px;
  font-weight: 650;
  color: #475569;
}

textarea,
input,
select {
  width: 100%;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid var(--border-strong);
  background: var(--surface);
  color: var(--text);
  font-size: 14px;
  line-height: 1.5;
  transition: border-color 0.16s ease, box-shadow 0.16s ease, background 0.16s ease;
}

textarea {
  min-height: 112px;
  resize: vertical;
  font-family: inherit;
}

textarea:focus,
input:focus,
select:focus,
.search-select-button:focus-visible,
button:focus-visible,
a:focus-visible {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.16);
}

button,
a,
.upload-button {
  touch-action: manipulation;
}

.options {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.option {
  flex: 1;
  min-width: 180px;
}

.search-picker {
  position: relative;
}

.search-select-button {
  width: 100%;
  min-height: 50px;
  padding: 0 16px;
  border-radius: 14px;
  border: 1px solid var(--border-strong);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  transition: border-color 0.16s ease, box-shadow 0.16s ease, background 0.16s ease;
}

.search-select-button.open,
.search-select-button:hover {
  border-color: var(--primary);
  background: #ffffff;
}

.search-chevron {
  color: var(--muted);
  font-size: 18px;
  line-height: 1;
}

.search-menu {
  position: absolute;
  z-index: 30;
  left: 0;
  right: 0;
  top: calc(100% + 8px);
  padding: 6px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--surface);
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.14);
}

.search-option {
  position: relative;
  width: 100%;
  min-height: 40px;
  padding: 8px 10px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--text);
  font: inherit;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  cursor: pointer;
  text-align: left;
}

.search-option:hover,
.search-option.active {
  background: var(--primary-soft);
  color: var(--primary-strong);
}

.search-option-info {
  width: 18px;
  height: 18px;
  border-radius: 999px;
  border: 1px solid #93c5fd;
  color: var(--primary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 750;
  flex: 0 0 auto;
}

.search-option-tooltip {
  position: absolute;
  right: 8px;
  top: calc(100% + 6px);
  z-index: 40;
  width: min(330px, 80vw);
  padding: 10px 12px;
  border-radius: 12px;
  background: #111827;
  color: #f8fafc;
  font-size: 12px;
  line-height: 1.55;
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.22);
  opacity: 0;
  pointer-events: none;
  transform: translateY(-4px);
  transition: opacity 0.16s ease, transform 0.16s ease;
}

.search-option-info:hover + .search-option-tooltip,
.search-option-info:focus + .search-option-tooltip {
  opacity: 1;
  transform: translateY(0);
}

.form-actions,
.status-bar,
.status-main,
.status-controls,
.task-chip-group,
.document-library-head,
.document-detail-header,
.tool-entry-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.form-actions,
.status-main,
.task-chip-group {
  flex-wrap: wrap;
}

.status-bar,
.document-library-head,
.document-detail-header,
.tool-entry-header {
  justify-content: space-between;
}

.submit,
.secondary-btn,
.back-btn,
.new-research-btn,
.document-delete-btn,
.link-btn,
.chip-action {
  border-radius: 12px;
  font: inherit;
  font-weight: 650;
  cursor: pointer;
  transition: background 0.16s ease, border-color 0.16s ease, color 0.16s ease, box-shadow 0.16s ease;
}

.submit,
.new-research-btn,
.upload-button {
  border: 1px solid var(--primary);
  background: var(--primary);
  color: #ffffff;
}

.submit,
.new-research-btn {
  min-height: 46px;
  padding: 0 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.submit:hover:not(:disabled),
.new-research-btn:hover,
.upload-button:hover:not(.disabled) {
  background: var(--primary-strong);
  border-color: var(--primary-strong);
}

.submit:disabled,
.back-btn:disabled,
.document-delete-btn:disabled,
.upload-button.disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.submit-label {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.spinner {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  animation: spin 1s linear infinite;
}

.secondary-btn,
.back-btn,
.link-btn,
.chip-action {
  border: 1px solid var(--border);
  background: var(--surface);
  color: #334155;
}

.secondary-btn,
.back-btn {
  min-height: 42px;
  padding: 0 14px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.secondary-btn:hover,
.back-btn:hover:not(:disabled),
.link-btn:hover,
.chip-action:hover {
  border-color: var(--border-strong);
  background: var(--surface-muted);
  color: var(--text);
}

.link-btn,
.chip-action {
  min-height: 28px;
  padding: 0 8px;
  font-size: 12px;
}

.error-chip,
.document-message {
  margin: 0;
  padding: 10px 12px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.5;
}

.error-chip,
.document-message.error {
  background: var(--danger-soft);
  border: 1px solid #fecaca;
  color: #991b1b;
}

.error-chip {
  margin-top: 16px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.error-chip svg {
  width: 18px;
  height: 18px;
  fill: currentColor;
}

.document-message.success {
  background: var(--success-soft);
  border: 1px solid #bbf7d0;
  color: #166534;
}

.hint.muted,
.muted,
.muted-text,
.status-meta,
.progress-text,
.task-intent,
.document-empty,
.document-meta,
.document-detail-header span,
.workflow-panel-header p,
.graph-node small,
.tool-subtitle,
.tool-entry-path {
  color: var(--muted);
}

.status-chip,
.task-label,
.task-status,
.tool-entry-note {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: fit-content;
  min-height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
  color: #334155;
  font-size: 12px;
  font-weight: 650;
}

.status-chip.active {
  background: var(--primary-soft);
  border-color: #bfdbfe;
  color: var(--primary-strong);
}

.status-chip .dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--primary);
}

.status-chip.active .dot {
  animation: pulse 1.7s ease-in-out infinite;
}

.result-workbench {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 18px;
  align-items: start;
}

.content-column,
.evidence-column {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.evidence-column {
  position: sticky;
  top: 18px;
}

.workflow-panel,
.tasks-list,
.task-detail,
.report-block,
.sources-block,
.tools-block,
.node-detail-block,
.summary-block,
.document-detail-panel,
.home-document-library {
  border: 1px solid var(--border);
  border-radius: 16px;
  background: var(--surface);
}

.workflow-panel,
.task-detail,
.report-block,
.sources-block,
.tools-block,
.node-detail-block,
.summary-block,
.home-document-library {
  padding: 18px;
}

.workflow-panel-header {
  margin-bottom: 14px;
}

.workflow-panel-header h3,
.tasks-list h3,
.task-header h3,
.report-block h3,
.sources-block h3,
.tools-block h3,
.node-detail-block h3,
.summary-block h3 {
  font-size: 16px;
  line-height: 1.35;
}

.workflow-map {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 4px;
}

.workflow-global-row,
.workflow-lane-nodes {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(168px, 1fr));
  gap: 10px;
}

.workflow-global-row.report-row {
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
}

.workflow-lanes {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.workflow-lane {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  gap: 10px;
  align-items: stretch;
}

.workflow-lane-label,
.graph-node,
.task-button,
.document-item-button,
.document-chunk {
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  text-align: left;
  font: inherit;
  transition: background 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
}

.workflow-lane-label {
  border-radius: 14px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
}

.workflow-lane-label span,
.path-label {
  color: var(--muted);
  font-size: 12px;
}

.workflow-lane-label strong {
  font-size: 13px;
  line-height: 1.35;
}

.graph-node {
  position: relative;
  min-height: 78px;
  border-radius: 14px;
  padding: 12px;
  display: grid;
  grid-template-columns: 10px 1fr;
  gap: 8px 10px;
  align-items: start;
}

.graph-node:hover,
.graph-node.selected,
.workflow-lane-label:hover,
.task-button:hover,
.document-item-button:hover,
.document-item-button.active,
.document-chunk:hover {
  border-color: #bfdbfe;
  background: var(--primary-soft);
}

.graph-node.selected,
.document-item-button.active {
  box-shadow: inset 0 0 0 1px #93c5fd;
}

.graph-node strong,
.graph-node small {
  grid-column: 2;
}

.graph-node strong {
  font-size: 13px;
  line-height: 1.35;
}

.graph-node small {
  font-size: 12px;
  line-height: 1.4;
}

.graph-node.in_progress .graph-node-dot,
.task-status.in_progress,
.task-status.running,
.task-status.processing {
  background: var(--warning-soft);
  border-color: #fde68a;
  color: #92400e;
}

.graph-node.in_progress .graph-node-dot {
  background: var(--warning);
}

.graph-node.completed,
.graph-node.succeeded {
  background: var(--success-soft);
  border-color: #bbf7d0;
}

.graph-node.completed .graph-node-dot,
.graph-node.succeeded .graph-node-dot {
  background: var(--success);
}

.graph-node.failed {
  background: var(--danger-soft);
  border-color: #fecaca;
}

.graph-node.failed .graph-node-dot {
  background: var(--danger);
}

.graph-node.skipped {
  background: var(--surface-muted);
}

.tasks-section {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.tasks-list {
  padding: 16px;
}

.tasks-list ul,
.sources-list,
.tool-list,
.document-list,
.task-notices ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.tasks-list ul,
.sources-list,
.tool-list,
.document-list,
.document-chunks,
.task-notices ul {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.task-button {
  width: 100%;
  border-radius: 12px;
  padding: 12px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.task-title {
  font-size: 13px;
  font-weight: 650;
  line-height: 1.4;
}

.task-status.completed {
  background: var(--success-soft);
  border-color: #bbf7d0;
  color: #166534;
}

.task-status.failed {
  background: var(--danger-soft);
  border-color: #fecaca;
  color: #991b1b;
}

.task-intent {
  margin: 8px 4px 0;
  font-size: 12px;
  line-height: 1.55;
}

.task-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.task-header p {
  margin: 6px 0 0;
  line-height: 1.55;
}

.task-notices {
  padding: 12px;
  margin-bottom: 14px;
  border-radius: 12px;
  border: 1px solid #fde68a;
  background: var(--warning-soft);
}

.task-notices h4 {
  margin: 0 0 8px;
  font-size: 13px;
  color: #92400e;
}

.task-notices li {
  color: #92400e;
  font-size: 12px;
  line-height: 1.5;
}

.block-pre,
.tool-pre {
  margin: 0;
  padding: 14px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
  color: #1f2937;
  font-family: "JetBrains Mono", "Fira Code", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
  overflow: auto;
}

.block-pre {
  max-height: none;
}

.tool-pre {
  max-height: 260px;
}

.summary-block,
.report-block {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.block-highlight {
  animation: highlight 1.1s ease;
}

.node-detail-title {
  margin: 8px 0;
  color: var(--text);
  font-weight: 700;
}

.source-item {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}

.source-item:last-child {
  border-bottom: 0;
}

.source-link {
  color: var(--primary-strong);
  text-decoration: none;
  font-size: 13px;
  font-weight: 650;
  line-height: 1.45;
}

.source-link::after {
  content: " ↗";
  font-size: 11px;
  color: var(--subtle);
}

.source-link:hover {
  color: var(--text);
}

.source-tooltip {
  display: none;
  position: absolute;
  right: 0;
  bottom: calc(100% + 8px);
  z-index: 25;
  width: min(420px, 82vw);
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  box-shadow: 0 18px 38px rgba(15, 23, 42, 0.14);
}

.source-tooltip p {
  margin: 0 0 8px;
  font-size: 12px;
  line-height: 1.55;
}

.source-tooltip p:last-child {
  margin-bottom: 0;
}

.source-item:hover .source-tooltip,
.source-item:focus-within .source-tooltip {
  display: block;
}

.tool-entry {
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tool-entry-title {
  color: var(--text);
  font-size: 13px;
  font-weight: 700;
}

.tool-entry-note {
  background: var(--success-soft);
  border-color: #bbf7d0;
  color: #166534;
}

.tool-entry-path {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
}

.path-text {
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar {
  width: 360px;
  min-width: 360px;
  height: 100vh;
  padding: 28px 22px;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 22px;
  overflow-y: auto;
}

.sidebar-header {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.sidebar-header h2 {
  font-size: 24px;
  line-height: 1.2;
  font-weight: 750;
}

.research-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item p {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: #334155;
}

.topic-display {
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
  color: var(--text) !important;
  font-weight: 650;
}

.progress-bar {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--surface-muted);
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
  background: var(--primary);
  transition: width 0.4s ease;
}

.document-library {
  margin-top: 2px;
}

.home-document-library {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.document-library-head span {
  color: var(--primary-strong);
  font-size: 12px;
  font-weight: 650;
}

.document-dropzone {
  padding: 14px;
  border-radius: 14px;
  border: 1px dashed var(--border-strong);
  background: var(--surface-soft);
}

.document-dropzone strong {
  display: block;
  margin-bottom: 6px;
  color: var(--text);
  font-size: 14px;
}

.document-dropzone p,
.document-empty,
.document-preview,
.document-chunk p {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
}

.document-dropzone p,
.document-empty {
  color: var(--muted) !important;
}

.upload-button {
  margin-top: 12px;
  width: 100%;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.upload-button input {
  display: none;
}

.document-list li {
  display: flex;
}

.document-item-button {
  width: 100%;
  padding: 11px 12px;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.document-name {
  max-width: 100%;
  color: var(--text);
  font-size: 13px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.document-meta {
  font-size: 12px;
}

.document-detail-panel {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: var(--surface-soft);
}

.document-detail-header div {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.document-detail-header strong {
  color: var(--text);
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.document-detail-header span {
  font-size: 12px;
}

.document-delete-btn {
  flex: 0 0 auto;
  min-height: 32px;
  padding: 0 10px;
  border: 1px solid #fecaca;
  background: var(--danger-soft);
  color: #991b1b;
  font-size: 12px;
}

.document-delete-btn:hover:not(:disabled) {
  background: #fee2e2;
}

.document-preview {
  padding: 10px;
  border-radius: 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: #334155 !important;
  word-break: break-word;
}

.document-chunk {
  width: 100%;
  padding: 10px;
  border-radius: 10px;
}

.document-chunk span {
  display: block;
  margin-bottom: 5px;
  color: var(--primary-strong);
  font-size: 12px;
  font-weight: 700;
}

.document-chunk p {
  color: #334155 !important;
  white-space: pre-wrap;
  word-break: break-word;
}

.sidebar-actions {
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.new-research-btn {
  width: 100%;
}


.workflow-toggle {
  flex: 0 0 auto;
}

.document-meta.processing,
.document-detail-header .processing {
  color: #92400e;
}

.document-meta.ready,
.document-detail-header .ready {
  color: #166534;
}

.document-meta.failed,
.document-detail-header .failed {
  color: #991b1b;
}

.source-headline {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.source-badge {
  flex: 0 0 auto;
  padding: 3px 8px;
  border-radius: 999px;
  background: var(--primary-soft);
  border: 1px solid #bfdbfe;
  color: var(--primary-strong);
  font-size: 11px;
  font-weight: 700;
}

.source-item.rag-hit {
  padding: 12px;
  border: 1px solid #bfdbfe;
  border-radius: 12px;
  background: var(--primary-soft);
}

.source-snippet {
  margin: 0;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid #dbeafe;
  background: #ffffff;
  color: #334155;
  font-size: 12px;
  line-height: 1.6;
}

.markdown-body {
  padding: 16px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
  color: #1f2937;
  line-height: 1.7;
  font-size: 14px;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 18px 0 10px;
  color: var(--text);
  line-height: 1.35;
}

.markdown-body :deep(h1:first-child),
.markdown-body :deep(h2:first-child),
.markdown-body :deep(h3:first-child) {
  margin-top: 0;
}

.markdown-body :deep(p) {
  margin: 0 0 12px;
}

.markdown-body :deep(ul) {
  margin: 0 0 12px;
  padding-left: 20px;
}

.markdown-body :deep(li) {
  margin: 4px 0;
}

.markdown-body :deep(code) {
  padding: 2px 5px;
  border-radius: 6px;
  background: #e2e8f0;
  font-family: "JetBrains Mono", "Fira Code", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
}

.markdown-body :deep(pre) {
  margin: 0 0 12px;
  padding: 12px;
  overflow: auto;
  border-radius: 10px;
  background: #111827;
  color: #f8fafc;
}

.markdown-body :deep(pre code) {
  padding: 0;
  background: transparent;
  color: inherit;
}

.markdown-body :deep(a) {
  color: var(--primary-strong);
  font-weight: 650;
  text-decoration: none;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 999px;
}

::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
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
    transform: scale(1.25);
    opacity: 0.58;
  }
}

@keyframes highlight {
  0% {
    border-color: #93c5fd;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
  }
  100% {
    border-color: var(--border);
    box-shadow: none;
  }
}

@media (max-width: 1180px) {
  .result-workbench {
    grid-template-columns: 1fr;
  }

  .evidence-column {
    position: static;
  }
}

@media (max-width: 1024px) {
  .sidebar {
    width: 320px;
    min-width: 320px;
  }

  .tasks-section {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .app-shell {
    padding: 32px 14px;
    overflow: auto;
  }

  .layout,
  .layout-fullscreen {
    flex-direction: column;
  }

  .layout-fullscreen {
    height: auto;
    min-height: 100vh;
  }

  .sidebar {
    width: 100%;
    min-width: 0;
    height: auto;
    max-height: none;
    border-right: 0;
    border-bottom: 1px solid var(--border);
  }

  .layout-fullscreen .panel-result {
    height: auto;
    min-height: 60vh;
  }

  .workflow-lane {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 600px) {
  .panel-centered,
  .panel {
    padding: 22px;
  }

  .panel-head,
  .status-bar,
  .task-header,
  .document-detail-header,
  .tool-entry-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .panel-form h1 {
    font-size: 24px;
  }

  .options,
  .form-actions,
  .status-controls {
    flex-direction: column;
    align-items: stretch;
  }

  .option,
  .submit,
  .secondary-btn {
    width: 100%;
  }

  .workflow-global-row,
  .workflow-global-row.report-row,
  .workflow-lane-nodes {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
  }
}
</style>
