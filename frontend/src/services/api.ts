import { getAccessToken } from "./auth";

const baseURL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";


async function authenticatedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {}
): Promise<Response> {
  const token = await getAccessToken();
  if (!token) {
    throw new Error("登录已失效，请重新登录");
  }
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  return fetch(input, { ...init, headers });
}
export interface ResearchRequest {
  topic: string;
  search_api?: string;
}

export interface ResearchStreamEvent {
  type: string;
  [key: string]: unknown;
}

export interface StreamOptions {
  signal?: AbortSignal;
}

export interface ResearchRunSummary {
  id: string;
  topic: string;
  search_api: string;
  created_at: string;
}

export interface ResearchRunTask {
  task_id: number;
  title: string;
  intent: string;
  query: string;
  status: string;
  summary: string | null;
  sources_summary: string | null;
  note_id: string | null;
  note_path: string | null;
}

export interface ResearchRunSource {
  id?: number;
  task_id: number;
  title: string;
  url: string;
  content: string;
}

export interface ResearchRunToolCall {
  event_id: number;
  agent: string;
  tool: string;
  parameters: Record<string, unknown>;
  result: string;
  task_id: number | null;
  note_id: string | null;
  step: number | null;
  created_at: string;
}

export interface ResearchRunDetail extends ResearchRunSummary {
  tasks: ResearchRunTask[];
  sources: ResearchRunSource[];
  report: {
    markdown: string;
    note_id: string | null;
    note_path: string | null;
  } | null;
  tool_calls: ResearchRunToolCall[];
}

export async function listResearchRuns(limit = 20): Promise<ResearchRunSummary[]> {
  const response = await authenticatedFetch(`${baseURL}/research/runs?limit=${limit}`);
  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    throw new Error(errorText || `研究历史请求失败，状态码：${response.status}`);
  }
  const payload = await response.json() as { runs: ResearchRunSummary[] };
  return payload.runs;
}

export async function getResearchRun(runId: string): Promise<ResearchRunDetail> {
  const response = await authenticatedFetch(`${baseURL}/research/runs/${encodeURIComponent(runId)}`);
  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    throw new Error(errorText || `研究历史请求失败，状态码：${response.status}`);
  }
  return await response.json() as ResearchRunDetail;
}

export async function runResearchStream(
  payload: ResearchRequest,
  onEvent: (event: ResearchStreamEvent) => void,
  options: StreamOptions = {}
): Promise<void> {
  const response = await authenticatedFetch(`${baseURL}/research/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream"
    },
    body: JSON.stringify(payload),
    signal: options.signal
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    throw new Error(
      errorText || `研究请求失败，状态码：${response.status}`
    );
  }

  const body = response.body;
  if (!body) {
    throw new Error("浏览器不支持流式响应，无法获取研究进度");
  }

  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const rawEvent = buffer.slice(0, boundary).trim();
      buffer = buffer.slice(boundary + 2);

      if (rawEvent.startsWith("data:")) {
        const dataPayload = rawEvent.slice(5).trim();
        if (dataPayload) {
          try {
            const event = JSON.parse(dataPayload) as ResearchStreamEvent;
            onEvent(event);

            if (event.type === "error" || event.type === "done") {
              return;
            }
          } catch (error) {
            console.error("解析流式事件失败：", error, dataPayload);
          }
        }
      }

      boundary = buffer.indexOf("\n\n");
    }

    if (done) {
      // 处理可能的尾巴事件
      if (buffer.trim()) {
        const rawEvent = buffer.trim();
        if (rawEvent.startsWith("data:")) {
          const dataPayload = rawEvent.slice(5).trim();
          if (dataPayload) {
            try {
              const event = JSON.parse(dataPayload) as ResearchStreamEvent;
              onEvent(event);
            } catch (error) {
              console.error("解析流式事件失败：", error, dataPayload);
            }
          }
        }
      }
      break;
    }
  }
}


export interface DocumentSummary {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  summary: string | null;
  status: "processing" | "ready" | "failed";
  error_message: string | null;
  processed_at: string | null;
  created_at: string;
  chunk_count: number;
}

export interface DocumentDetail extends DocumentSummary {
  raw_text: string;
  chunks: Array<{
    id: string;
    document_id: string;
    document_title: string;
    chunk_index: number;
    text: string;
    metadata: Record<string, unknown>;
  }>;
}

export async function uploadDocument(file: File): Promise<DocumentSummary> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await authenticatedFetch(`${baseURL}/documents/upload`, {
    method: "POST",
    body: formData
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    throw new Error(errorText || `文档请求失败，状态码：${response.status}`);
  }

  const payload = await response.json() as { document: DocumentSummary };
  return payload.document;
}

export async function listDocuments(): Promise<DocumentSummary[]> {
  const response = await authenticatedFetch(`${baseURL}/documents`);

  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    throw new Error(errorText || `文档请求失败，状态码：${response.status}`);
  }

  const payload = await response.json() as { documents: DocumentSummary[] };
  return payload.documents;
}

export async function getDocument(documentId: string): Promise<DocumentDetail> {
  const response = await authenticatedFetch(`${baseURL}/documents/${documentId}`);

  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    throw new Error(errorText || `文档请求失败，状态码：${response.status}`);
  }

  return await response.json() as DocumentDetail;
}
export async function retryDocument(documentId: string): Promise<DocumentSummary> {
  const response = await authenticatedFetch(`${baseURL}/documents/${documentId}/retry`, {
    method: "POST"
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    throw new Error(errorText || `retry document failed: ${response.status}`);
  }

  const payload = await response.json() as { document: DocumentSummary };
  return payload.document;
}

export async function deleteDocument(documentId: string): Promise<void> {
  const response = await authenticatedFetch(`${baseURL}/documents/${documentId}`, {
    method: "DELETE"
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    throw new Error(errorText || `删除文档失败，状态码：${response.status}`);
  }
}
