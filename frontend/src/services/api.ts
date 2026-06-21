const baseURL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

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

export async function runResearchStream(
  payload: ResearchRequest,
  onEvent: (event: ResearchStreamEvent) => void,
  options: StreamOptions = {}
): Promise<void> {
  const response = await fetch(`${baseURL}/research/stream`, {
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

  const response = await fetch(`${baseURL}/documents/upload`, {
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
  const response = await fetch(`${baseURL}/documents`);

  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    throw new Error(errorText || `文档请求失败，状态码：${response.status}`);
  }

  const payload = await response.json() as { documents: DocumentSummary[] };
  return payload.documents;
}

export async function getDocument(documentId: string): Promise<DocumentDetail> {
  const response = await fetch(`${baseURL}/documents/${documentId}`);

  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    throw new Error(errorText || `文档请求失败，状态码：${response.status}`);
  }

  return await response.json() as DocumentDetail;
}
export async function retryDocument(documentId: string): Promise<DocumentSummary> {
  const response = await fetch(`${baseURL}/documents/${documentId}/retry`, {
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
  const response = await fetch(`${baseURL}/documents/${documentId}`, {
    method: "DELETE"
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    throw new Error(errorText || `删除文档失败，状态码：${response.status}`);
  }
}
