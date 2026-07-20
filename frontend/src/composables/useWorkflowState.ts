import { computed, ref, type Ref } from "vue";

import { parseSources, type HistoryReplayState } from "../services/historyReplay";
import type { ResearchStreamEvent } from "../services/api";
import type { SourceItem, TodoTaskView, WorkflowEdgeView, WorkflowNodeView } from "../types";

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

const DEFAULT_WORKFLOW_NODES: WorkflowNodeView[] = [
  { key: "global:plan_tasks", id: "global:plan_tasks", node: "plan_tasks", label: "规划研究任务", status: "pending", detail: "", scope: "global", taskId: null, taskTitle: "", dependsOn: [] },
  { key: "global:dispatch_tasks", id: "global:dispatch_tasks", node: "dispatch_tasks", label: "分发并行任务", status: "pending", detail: "", scope: "global", taskId: null, taskTitle: "", dependsOn: ["global:plan_tasks"] },
  { key: "global:join_tasks", id: "global:join_tasks", node: "join_tasks", label: "汇总任务结果", status: "pending", detail: "", scope: "global", taskId: null, taskTitle: "", dependsOn: [] },
  { key: "global:write_report", id: "global:write_report", node: "write_report", label: "撰写最终报告", status: "pending", detail: "", scope: "global", taskId: null, taskTitle: "", dependsOn: ["global:join_tasks"] },
  { key: "global:persist_report", id: "global:persist_report", node: "persist_report", label: "保存最终报告", status: "pending", detail: "", scope: "global", taskId: null, taskTitle: "", dependsOn: ["global:write_report"] }
];

function extractOptionalString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed || null;
}

function ensureRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
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
  if (inCode) html.push(`<pre><code>${codeLines.join("\n")}</code></pre>`);
  return html.join("");
}

function pulse(flag: Ref<boolean>): void {
  flag.value = false;
  requestAnimationFrame(() => {
    flag.value = true;
    window.setTimeout(() => { flag.value = false; }, 1200);
  });
}

export function useWorkflowState() {
  const progressLogs = ref<string[]>([]);
  const workflowCollapsed = ref(false);
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

  const totalTasks = computed(() => todoTasks.value.length);
  const completedTasks = computed(() => todoTasks.value.filter((task) => task.status === "completed").length);
  const visibleWorkflowNodes = computed(() => workflowNodes.value.length ? workflowNodes.value : DEFAULT_WORKFLOW_NODES);
  const completedWorkflowNodes = computed(() => visibleWorkflowNodes.value.filter((node) => ["completed", "skipped"].includes(node.status)).length);
  const globalWorkflowNodes = computed(() => visibleWorkflowNodes.value.filter((node) => node.scope === "global" && ["plan_tasks", "dispatch_tasks"].includes(node.node)));
  const reportWorkflowNodes = computed(() => visibleWorkflowNodes.value.filter((node) => node.scope === "global" && ["join_tasks", "write_report", "persist_report"].includes(node.node)));
  const taskWorkflowRows = computed(() => todoTasks.value.map((task) => ({ task, nodes: visibleWorkflowNodes.value.filter((node) => node.taskId === task.id) })));
  const selectedWorkflowNode = computed(() => selectedWorkflowNodeId.value ? visibleWorkflowNodes.value.find((node) => node.id === selectedWorkflowNodeId.value) ?? null : null);
  const currentTask = computed(() => activeTaskId.value !== null ? todoTasks.value.find((task) => task.id === activeTaskId.value) ?? null : todoTasks.value[0] ?? null);
  const currentTaskSources = computed(() => currentTask.value?.sourceItems ?? []);
  const currentTaskSummary = computed(() => currentTask.value?.summary ?? "");
  const currentTaskTitle = computed(() => currentTask.value?.title ?? "");
  const currentTaskIntent = computed(() => currentTask.value?.intent ?? "");
  const currentTaskQuery = computed(() => currentTask.value?.query ?? "");
  const currentTaskNoteId = computed(() => currentTask.value?.noteId ?? "");
  const currentTaskNotePath = computed(() => currentTask.value?.notePath ?? "");
  const currentTaskToolCalls = computed(() => currentTask.value?.toolCalls ?? []);
  const renderedReportHtml = computed(() => renderMarkdown(reportMarkdown.value));

  function addLog(message: string): void {
    progressLogs.value.push(message);
  }

  function formatTaskStatus(status: string): string {
    return TASK_STATUS_LABEL[status] ?? status;
  }

  function formatWorkflowStatus(status: string): string {
    return WORKFLOW_STATUS_LABEL[status] ?? status;
  }

  function workflowTaskTitle(taskId: number | null): string {
    return taskId ? todoTasks.value.find((task) => task.id === taskId)?.title ?? "任务" : "全局流程";
  }

  function reset(): void {
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

  function restore(replay: HistoryReplayState): void {
    reset();
    todoTasks.value = replay.tasks;
    reportMarkdown.value = replay.reportMarkdown || "历史运行未保存最终报告";
    workflowNodes.value = replay.workflowNodes;
    workflowEdges.value = replay.workflowEdges;
    activeTaskId.value = replay.tasks[0]?.id ?? null;
    selectedWorkflowNodeId.value = replay.workflowNodes[0]?.id ?? null;
  }

  function findTask(taskId: unknown): TodoTaskView | undefined {
    const numeric = typeof taskId === "number" ? taskId : typeof taskId === "string" ? Number(taskId) : NaN;
    return Number.isNaN(numeric) ? undefined : todoTasks.value.find((task) => task.id === numeric);
  }

  function applyNoteMetadata(task: TodoTaskView, payload: Record<string, unknown>): void {
    const noteId = extractOptionalString(payload.note_id);
    const notePath = extractOptionalString(payload.note_path);
    if (noteId) task.noteId = noteId;
    if (notePath) task.notePath = notePath;
  }

  function upsertTaskMetadata(task: TodoTaskView, payload: Record<string, unknown>): void {
    if (typeof payload.title === "string" && payload.title.trim()) task.title = payload.title.trim();
    if (typeof payload.intent === "string" && payload.intent.trim()) task.intent = payload.intent.trim();
    if (typeof payload.query === "string" && payload.query.trim()) task.query = payload.query.trim();
  }

  function upsertWorkflowNode(payload: Record<string, unknown>): void {
    const node = extractOptionalString(payload.node);
    if (!node) return;
    const rawTaskId = payload.task_id;
    const parsedTaskId = typeof rawTaskId === "number" ? rawTaskId : typeof rawTaskId === "string" ? Number(rawTaskId) : null;
    const taskId = typeof parsedTaskId === "number" && Number.isFinite(parsedTaskId) ? parsedTaskId : null;
    const nodeId = extractOptionalString(payload.node_id) ?? "";
    const scope = extractOptionalString(payload.scope) ?? "global";
    const key = nodeId || `${scope}:${taskId ?? "global"}:${node}`;
    const next: WorkflowNodeView = {
      key,
      id: key,
      node,
      label: extractOptionalString(payload.label) ?? node,
      status: extractOptionalString(payload.status) ?? "pending",
      detail: extractOptionalString(payload.detail) ?? "",
      scope,
      taskId,
      taskTitle: taskId ? workflowTaskTitle(taskId) : "",
      dependsOn: Array.isArray(payload.depends_on) ? payload.depends_on.filter((item): item is string => typeof item === "string") : []
    };
    const index = workflowNodes.value.findIndex((item) => item.key === key);
    if (index >= 0) workflowNodes.value[index] = next;
    else workflowNodes.value.push(next);
  }

  function applyWorkflowGraph(payload: Record<string, unknown>): void {
    const nodes = Array.isArray(payload.nodes) ? payload.nodes.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item)) : [];
    const edges = Array.isArray(payload.edges) ? payload.edges.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item)) : [];
    workflowNodes.value = nodes.map((item, index) => {
      const id = extractOptionalString(item.id) ?? extractOptionalString(item.node) ?? `node-${index}`;
      const rawTaskId = item.task_id;
      const parsedTaskId = typeof rawTaskId === "number" ? rawTaskId : typeof rawTaskId === "string" ? Number(rawTaskId) : null;
      const taskId = typeof parsedTaskId === "number" && Number.isFinite(parsedTaskId) ? parsedTaskId : null;
      return {
        key: id,
        id,
        node: extractOptionalString(item.node) ?? id,
        label: extractOptionalString(item.label) ?? id,
        status: extractOptionalString(item.status) ?? "pending",
        detail: "",
        scope: extractOptionalString(item.scope) ?? "global",
        taskId,
        taskTitle: extractOptionalString(item.task_title) ?? workflowTaskTitle(taskId),
        dependsOn: []
      };
    });
    workflowEdges.value = edges.map((item) => ({ from: extractOptionalString(item.from) ?? "", to: extractOptionalString(item.to) ?? "" })).filter((edge) => edge.from && edge.to);
  }

  function consumeEvent(event: ResearchStreamEvent, topic: string): void {
    const payload = event as Record<string, unknown>;
    if (event.type === "status") {
      const message = extractOptionalString(event.message) ?? "流程状态更新";
      addLog(message);
      const task = findTask(payload.task_id);
      if (task) {
        task.notices.push(message);
        applyNoteMetadata(task, payload);
      }
      return;
    }
    if (event.type === "workflow_node") {
      upsertWorkflowNode(payload);
      const nodeId = extractOptionalString(payload.node_id);
      if (nodeId) selectedWorkflowNodeId.value = nodeId;
      const label = extractOptionalString(payload.label) ?? "工作流节点";
      const status = extractOptionalString(payload.status) ?? "";
      const detail = extractOptionalString(payload.detail);
      if (status === "in_progress") addLog(`${label}开始`);
      else if (detail) addLog(`${label}：${detail}`);
      return;
    }
    if (event.type === "workflow_graph") {
      applyWorkflowGraph(payload);
      addLog("已加载 LangGraph 工作流拓扑");
      return;
    }
    if (event.type === "todo_list") {
      const tasks = Array.isArray(event.tasks) ? event.tasks.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item)) : [];
      todoTasks.value = tasks.map((item, index) => {
        const rawId = typeof item.id === "number" ? item.id : typeof item.id === "string" ? Number(item.id) : index + 1;
        const id = Number.isFinite(rawId) ? Number(rawId) : index + 1;
        return {
          id,
          title: extractOptionalString(item.title) ?? `任务${id}`,
          intent: extractOptionalString(item.intent) ?? "探索与主题相关的关键信息",
          query: extractOptionalString(item.query) ?? topic,
          status: extractOptionalString(item.status) ?? "pending",
          summary: "",
          sourcesSummary: "",
          sourceItems: [],
          notices: [],
          noteId: extractOptionalString(item.note_id),
          notePath: extractOptionalString(item.note_path),
          toolCalls: [],
          searchExecution: null
        };
      });
      activeTaskId.value = todoTasks.value[0]?.id ?? null;
      addLog(todoTasks.value.length ? "已生成任务清单" : "未生成任务清单，使用默认任务继续");
      return;
    }
    if (event.type === "task_status") {
      const task = findTask(event.task_id);
      if (!task) return;
      upsertTaskMetadata(task, payload);
      applyNoteMetadata(task, payload);
      const status = extractOptionalString(event.status) ?? task.status;
      task.status = status;
      if (status === "in_progress") {
        Object.assign(task, { summary: "", sourcesSummary: "", sourceItems: [], notices: [] });
        activeTaskId.value = task.id;
        addLog(`开始执行任务：${task.title}`);
      } else if (status === "completed") {
        const summary = extractOptionalString(event.summary);
        const sources = extractOptionalString(event.sources_summary);
        if (summary) task.summary = summary;
        if (sources) {
          task.sourcesSummary = sources;
          task.sourceItems = parseSources(sources);
        }
        addLog(`完成任务：${task.title}`);
        if (activeTaskId.value === task.id) {
          pulse(summaryHighlight);
          pulse(sourcesHighlight);
        }
      } else if (status === "skipped") addLog(`任务跳过：${task.title}`);
      return;
    }
    if (event.type === "sources") {
      const task = findTask(event.task_id);
      if (!task) return;
      const latestText = [payload.latest_sources, payload.sources_summary, payload.raw_context]
        .map((value) => typeof value === "string" ? value.trim() : "")
        .find(Boolean);
      if (latestText) {
        task.sourcesSummary = latestText;
        task.sourceItems = parseSources(latestText);
        if (activeTaskId.value === task.id) pulse(sourcesHighlight);
        addLog(`已更新任务来源：${task.title}`);
      }
      if (typeof payload.backend === "string") addLog(`当前使用搜索后端：${payload.backend}`);
      applyNoteMetadata(task, payload);
      return;
    }
    if (event.type === "search_backend") {
      const task = findTask(payload.task_id);
      if (!task) return;
      const actualBackend = extractOptionalString(payload.actual_backend);
      if (!actualBackend) return;
      task.searchExecution = {
        requestedBackend: extractOptionalString(payload.requested_backend) ?? actualBackend,
        actualBackend,
        fallbackReason: extractOptionalString(payload.fallback_reason)
      };
      addLog(
        task.searchExecution.fallbackReason
          ? `实际使用搜索后端：${actualBackend}（已降级）`
          : `实际使用搜索后端：${actualBackend}`
      );
      return;
    }
    if (event.type === "task_summary_chunk") {
      const task = findTask(event.task_id);
      if (!task) return;
      task.summary += typeof event.content === "string" ? event.content : "";
      applyNoteMetadata(task, payload);
      if (activeTaskId.value === task.id) pulse(summaryHighlight);
      return;
    }
    if (event.type === "tool_call") {
      const task = findTask(payload.task_id);
      const agent = extractOptionalString(payload.agent) ?? "Agent";
      const tool = extractOptionalString(payload.tool) ?? "tool";
      const noteId = extractOptionalString(payload.note_id);
      const notePath = extractOptionalString(payload.note_path);
      if (task) {
        task.toolCalls.push({
          eventId: typeof payload.event_id === "number" ? payload.event_id : Date.now(),
          agent,
          tool,
          parameters: ensureRecord(payload.parameters),
          result: typeof payload.result === "string" ? payload.result : "",
          noteId,
          notePath,
          timestamp: Date.now()
        });
        if (noteId) task.noteId = noteId;
        if (notePath) task.notePath = notePath;
        addLog(noteId ? `${agent} 调用了 ${tool}（任务 ${task.id}，笔记 ${noteId}）` : `${agent} 调用了 ${tool}（任务 ${task.id}）`);
        if (activeTaskId.value === task.id) pulse(toolHighlight);
      } else addLog(`${agent} 调用了 ${tool}`);
      return;
    }
    if (event.type === "final_report") {
      reportMarkdown.value = extractOptionalString(event.report) ?? "报告生成失败，未获得有效内容";
      pulse(reportHighlight);
      addLog("最终报告已生成");
      return;
    }
    if (event.type === "error") addLog("研究失败，已停止流程");
  }

  async function copyNotePath(path: string | null | undefined): Promise<void> {
    if (!path) return;
    try {
      await navigator.clipboard.writeText(path);
      addLog(`已复制笔记路径：${path}`);
    } catch (error) {
      console.warn("无法直接复制到剪贴板", error);
      window.prompt("复制以下笔记路径", path);
      addLog("请手动复制笔记路径");
    }
  }

  function formatToolParameters(parameters: Record<string, unknown>): string {
    try { return JSON.stringify(parameters, null, 2); }
    catch (error) {
      console.warn("无法格式化工具参数", error, parameters);
      return Object.entries(parameters).map(([key, value]) => `${key}: ${String(value)}`).join("\n");
    }
  }

  function formatToolResult(result: string): string {
    const trimmed = result.trim();
    return trimmed.length > 900 ? `${trimmed.slice(0, 900)}…` : trimmed;
  }

  function isDocumentSource(item: SourceItem): boolean {
    return item.url.startsWith("document://") || item.raw.includes("document://") || item.title.includes("document://");
  }

  return {
    progressLogs, workflowCollapsed, todoTasks, activeTaskId, reportMarkdown,
    workflowNodes, workflowEdges, selectedWorkflowNodeId, summaryHighlight,
    sourcesHighlight, reportHighlight, toolHighlight, totalTasks, completedTasks,
    visibleWorkflowNodes, completedWorkflowNodes, globalWorkflowNodes,
    reportWorkflowNodes, taskWorkflowRows, selectedWorkflowNode, currentTask,
    currentTaskSources, currentTaskSummary, currentTaskTitle, currentTaskIntent,
    currentTaskQuery, currentTaskNoteId, currentTaskNotePath, currentTaskToolCalls,
    renderedReportHtml, reset, restore, consumeEvent, addLog, formatTaskStatus,
    formatWorkflowStatus, workflowTaskTitle, copyNotePath, formatToolParameters,
    formatToolResult, isDocumentSource
  };
}
