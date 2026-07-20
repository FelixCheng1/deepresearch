export interface SourceItem {
  title: string;
  url: string;
  snippet: string;
  raw: string;
}

export interface ToolCallLog {
  eventId: number;
  agent: string;
  tool: string;
  parameters: Record<string, unknown>;
  result: string;
  noteId: string | null;
  notePath: string | null;
  timestamp: number;
}

export interface SearchExecutionView {
  requestedBackend: string;
  actualBackend: string;
  fallbackReason: string | null;
}

export interface TodoTaskView {
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
  searchExecution: SearchExecutionView | null;
}

export interface WorkflowNodeView {
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

export interface WorkflowEdgeView {
  from: string;
  to: string;
}

export interface SearchOptionItem {
  value: string;
  label: string;
  detail: string;
}
