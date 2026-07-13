import type { ResearchRunDetail, ResearchRunSource } from "./api";
import type {
  SourceItem,
  TodoTaskView,
  ToolCallLog,
  WorkflowEdgeView,
  WorkflowNodeView
} from "../types";

export interface HistoryReplayState {
  tasks: TodoTaskView[];
  reportMarkdown: string;
  workflowNodes: WorkflowNodeView[];
  workflowEdges: WorkflowEdgeView[];
}

export function parseSources(raw: string): SourceItem[] {
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
    if (normalized.title || normalized.url || normalized.snippet || normalized.raw) {
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
      current = { title: titlePart?.trim() || "", url: urlPart?.trim() || "", snippet: "", raw: "" };
      continue;
    }
    if (/^(Source|信息来源)\s*:/.test(trimmed)) {
      flush();
      const [, titlePart = ""] = trimmed.split(/:\s*(.+)/);
      current = { title: titlePart.trim(), url: "", snippet: "", raw: "" };
      continue;
    }
    if (/^URL\s*:/.test(trimmed)) {
      ensureCurrent();
      const [, urlPart = ""] = trimmed.split(/:\s*(.+)/);
      current!.url = urlPart.trim();
      continue;
    }
    if (/^(Most relevant content from source|信息内容)\s*:/.test(trimmed)) {
      ensureCurrent();
      const [, contentPart = ""] = trimmed.split(/:\s*(.+)/);
      current!.snippet = contentPart.trim();
      continue;
    }
    if (/^(Full source content limited to|信息内容限制为)\s*:/.test(trimmed)) {
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

export function buildHistoryReplay(run: ResearchRunDetail): HistoryReplayState {
  const sourcesByTask = new Map<number, ResearchRunSource[]>();
  for (const source of run.sources ?? []) {
    const bucket = sourcesByTask.get(source.task_id) ?? [];
    bucket.push(source);
    sourcesByTask.set(source.task_id, bucket);
  }

  const callsByTask = new Map<number, ToolCallLog[]>();
  for (const call of run.tool_calls ?? []) {
    if (call.task_id === null) {
      continue;
    }
    const bucket = callsByTask.get(call.task_id) ?? [];
    const timestamp = Date.parse(call.created_at);
    bucket.push({
      eventId: call.event_id,
      agent: call.agent,
      tool: call.tool,
      parameters: call.parameters ?? {},
      result: call.result ?? "",
      noteId: call.note_id,
      notePath: null,
      timestamp: Number.isNaN(timestamp) ? 0 : timestamp
    });
    callsByTask.set(call.task_id, bucket);
  }

  const tasks = (run.tasks ?? []).map<TodoTaskView>((task) => {
    const sourceItems = mergeSources(
      parseSources(task.sources_summary ?? ""),
      sourcesByTask.get(task.task_id) ?? []
    );
    const toolCalls = callsByTask.get(task.task_id) ?? [];
    for (const call of toolCalls) {
      if (call.noteId && call.noteId === task.note_id) {
        call.notePath = task.note_path;
      }
    }
    return {
      id: task.task_id,
      title: task.title,
      intent: task.intent,
      query: task.query,
      status: task.status,
      summary: task.summary ?? "",
      sourcesSummary: task.sources_summary ?? "",
      sourceItems,
      notices: [],
      noteId: task.note_id,
      notePath: task.note_path,
      toolCalls
    };
  });

  const { nodes, edges } = buildReplayWorkflow(tasks, Boolean(run.report?.markdown));
  return {
    tasks,
    reportMarkdown: run.report?.markdown ?? "",
    workflowNodes: nodes,
    workflowEdges: edges
  };
}

function mergeSources(parsed: SourceItem[], stored: ResearchRunSource[]): SourceItem[] {
  const items = [...parsed];
  const seen = new Set(items.map((item) => `${item.url}\u0000${item.title}`));
  for (const source of stored) {
    const key = `${source.url}\u0000${source.title}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    items.push({
      title: source.title || source.url,
      url: source.url,
      snippet: source.content,
      raw: source.content
    });
  }
  return items;
}

function buildReplayWorkflow(
  tasks: TodoTaskView[],
  hasReport: boolean
): { nodes: WorkflowNodeView[]; edges: WorkflowEdgeView[] } {
  const globalStatus = hasReport ? "completed" : "skipped";
  const nodes: WorkflowNodeView[] = [
    workflowNode("global:plan_tasks", "plan_tasks", "规划研究任务", "global", globalStatus),
    workflowNode("global:dispatch_tasks", "dispatch_tasks", "分发并行任务", "global", globalStatus),
    workflowNode("global:join_tasks", "join_tasks", "汇总任务结果", "global", globalStatus),
    workflowNode("global:write_report", "write_report", "撰写最终报告", "global", globalStatus),
    workflowNode("global:persist_report", "persist_report", "保存最终报告", "global", globalStatus)
  ];
  const edges: WorkflowEdgeView[] = [
    { from: "global:plan_tasks", to: "global:dispatch_tasks" },
    { from: "global:join_tasks", to: "global:write_report" },
    { from: "global:write_report", to: "global:persist_report" }
  ];

  for (const task of tasks) {
    const prefix = `task:${task.id}`;
    const taskStatus = task.status === "pending" ? "pending" : task.status;
    const retrievalStatus = task.sourceItems.length ? "completed" : "skipped";
    const specs = [
      ["prepare_task", "准备任务", taskStatus === "pending" ? "pending" : "completed"],
      ["retrieve_documents", "检索文档库", retrievalStatus],
      ["search_web", "执行网页搜索", retrievalStatus],
      ["summarize_task", "总结任务", taskStatus],
      ["persist_task", "保存任务结果", taskStatus]
    ] as const;
    const ids = specs.map(([node, label, status]) => {
      const id = `${prefix}:${node}`;
      nodes.push(workflowNode(id, node, label, "task", status, task));
      return id;
    });
    edges.push({ from: "global:dispatch_tasks", to: ids[0] });
    for (let index = 0; index < ids.length - 1; index += 1) {
      edges.push({ from: ids[index], to: ids[index + 1] });
    }
    edges.push({ from: ids[ids.length - 1], to: "global:join_tasks" });
  }
  return { nodes, edges };
}

function workflowNode(
  id: string,
  node: string,
  label: string,
  scope: string,
  status: string,
  task?: TodoTaskView
): WorkflowNodeView {
  return {
    key: id,
    id,
    node,
    label,
    status,
    detail: "由持久化历史快照重建",
    scope,
    taskId: task?.id ?? null,
    taskTitle: task?.title ?? "",
    dependsOn: []
  };
}
