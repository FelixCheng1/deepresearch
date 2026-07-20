import { ref } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  getCapabilities: vi.fn(),
  runResearchStream: vi.fn(),
  listResearchRuns: vi.fn(),
  getResearchRun: vi.fn(),
  listDocuments: vi.fn(),
  getDocument: vi.fn(),
  uploadDocument: vi.fn(),
  retryDocument: vi.fn(),
  deleteDocument: vi.fn()
}));

vi.mock("../services/api", () => apiMocks);

import { useDocuments } from "../composables/useDocuments";
import { useResearchFlow } from "../composables/useResearchFlow";
import { useResearchHistory } from "../composables/useResearchHistory";
import { useWorkflowState } from "../composables/useWorkflowState";

const runDetail = {
  id: "run-1",
  topic: "研究主题",
  search_api: "duckduckgo",
  created_at: "2026-07-20T00:00:00Z",
  tasks: [],
  sources: [],
  report: { markdown: "# 报告", note_id: null, note_path: null },
  tool_calls: []
};

beforeEach(() => {
  vi.clearAllMocks();
  apiMocks.getCapabilities.mockResolvedValue({
    search: {
      default_engine: "tavily",
      default_available: true,
      engines: [
        { id: "advanced", label: "智能降级", description: "自动降级" },
        { id: "duckduckgo", label: "DuckDuckGo", description: "免费搜索" },
        { id: "tavily", label: "Tavily", description: "生产搜索" }
      ]
    }
  });
});
afterEach(() => vi.useRealTimers());

describe("工作台 composables", () => {
  it("工作流状态归并任务事件和最终报告", () => {
    const workflow = useWorkflowState();
    workflow.consumeEvent({ type: "todo_list", tasks: [{ id: 1, title: "背景", status: "pending" }] }, "主题");
    workflow.consumeEvent({ type: "task_status", task_id: 1, status: "completed", summary: "完成" }, "主题");
    workflow.consumeEvent({ type: "final_report", report: "# 结论" }, "主题");

    expect(workflow.todoTasks.value[0]).toMatchObject({ title: "背景", status: "completed", summary: "完成" });
    expect(workflow.reportMarkdown.value).toBe("# 结论");
    expect(workflow.completedTasks.value).toBe(1);
  });

  it("研究流保留流式事件协议并在结束后刷新历史", async () => {
    const workflow = useWorkflowState();
    const research = useResearchFlow(workflow);
    const settled = vi.fn();
    research.form.topic = "测试研究";
    apiMocks.runResearchStream.mockImplementation(async (_payload: unknown, onEvent: (event: { type: string; report?: string }) => void) => {
      onEvent({ type: "final_report", report: "报告内容" });
    });

    await research.handleSubmit(3, settled);

    expect(apiMocks.runResearchStream).toHaveBeenCalled();
    expect(research.researchDocumentCount.value).toBe(3);
    expect(workflow.reportMarkdown.value).toBe("报告内容");
    expect(settled).toHaveBeenCalledOnce();
  });

  it("研究流只使用后端能力接口返回的搜索选项", async () => {
    const research = useResearchFlow(useWorkflowState());

    await research.loadCapabilities();

    expect(research.searchOptionItems.value.map((item) => item.value)).toEqual([
      "",
      "advanced",
      "duckduckgo",
      "tavily"
    ]);
    expect(research.searchOptionItems.value.some((item) => item.value === "perplexity")).toBe(false);
    expect(research.selectedSearchLabel.value).toContain("tavily");
  });

  it("默认后端不可用时自动选择第一项真实能力", async () => {
    apiMocks.getCapabilities.mockResolvedValue({
      search: {
        default_engine: "perplexity",
        default_available: false,
        engines: [
          { id: "advanced", label: "智能降级", description: "自动降级" },
          { id: "duckduckgo", label: "DuckDuckGo", description: "免费搜索" }
        ]
      }
    });
    const research = useResearchFlow(useWorkflowState());

    await research.loadCapabilities();

    expect(research.searchOptionItems.value.map((item) => item.value)).toEqual([
      "advanced",
      "duckduckgo"
    ]);
    expect(research.form.searchApi).toBe("advanced");
  });

  it("工作流记录实际搜索后端和降级原因", () => {
    const workflow = useWorkflowState();
    workflow.consumeEvent({ type: "todo_list", tasks: [{ id: 1, title: "背景", status: "pending" }] }, "主题");
    workflow.consumeEvent({
      type: "search_backend",
      task_id: 1,
      requested_backend: "tavily",
      actual_backend: "duckduckgo",
      fallback_reason: "Tavily 请求失败"
    }, "主题");

    expect(workflow.todoTasks.value[0].searchExecution).toEqual({
      requestedBackend: "tavily",
      actualBackend: "duckduckgo",
      fallbackReason: "Tavily 请求失败"
    });
  });

  it("历史 composable 返回回放快照而不直接改写工作流", async () => {
    apiMocks.listResearchRuns.mockResolvedValue([{ id: "run-1", topic: "研究主题", search_api: "", created_at: "2026-07-20" }]);
    apiMocks.getResearchRun.mockResolvedValue(runDetail);
    const history = useResearchHistory();

    await history.refreshResearchRuns();
    const loaded = await history.loadResearchRun("run-1");

    expect(history.researchRuns.value).toHaveLength(1);
    expect(loaded?.replay.reportMarkdown).toBe("# 报告");
  });

  it("历史回放从持久化搜索工具记录恢复后端信息", async () => {
    apiMocks.getResearchRun.mockResolvedValue({
      ...runDetail,
      tasks: [{
        task_id: 1,
        title: "背景",
        intent: "了解背景",
        query: "topic",
        status: "completed",
        summary: "完成",
        sources_summary: "",
        note_id: null,
        note_path: null
      }],
      tool_calls: [{
        event_id: -1,
        agent: "研究检索代理",
        tool: "search",
        parameters: { requested_backend: "advanced" },
        result: JSON.stringify({
          requested_backend: "advanced",
          actual_backend: "duckduckgo",
          fallback_reason: "Tavily 未配置 API 密钥"
        }),
        task_id: 1,
        note_id: null,
        step: 1,
        created_at: "2026-07-20T00:00:00Z"
      }]
    });
    const loaded = await useResearchHistory().loadResearchRun("run-1");

    expect(loaded?.replay.tasks[0].searchExecution?.actualBackend).toBe("duckduckgo");
    expect(loaded?.replay.tasks[0].searchExecution?.fallbackReason).toContain("Tavily");
  });

  it("文档 composable 启动轮询并在销毁时清理计时器", async () => {
    vi.useFakeTimers();
    apiMocks.listDocuments.mockResolvedValue([{ id: "doc-1", filename: "a.md", content_type: "text/markdown", size_bytes: 10, summary: null, status: "processing", error_message: null, processed_at: null, created_at: "2026-07-20", chunk_count: 0 }]);
    const documents = useDocuments(ref(false), ref(false));

    await documents.refreshDocuments();
    expect(vi.getTimerCount()).toBe(1);
    documents.dispose();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("再次选择同一文档时收起详情", async () => {
    apiMocks.getDocument.mockResolvedValue({
      id: "doc-1", filename: "agent.md", content_type: "text/markdown", size_bytes: 10,
      summary: "摘要", status: "ready", error_message: null, processed_at: "2026-07-20",
      created_at: "2026-07-20", chunk_count: 1, raw_text: "正文", chunks: []
    });
    const documents = useDocuments(ref(false), ref(false));

    await documents.selectDocument("doc-1");
    expect(documents.selectedDocumentId.value).toBe("doc-1");

    await documents.selectDocument("doc-1");
    expect(documents.selectedDocumentId.value).toBeNull();
    expect(documents.selectedDocument.value).toBeNull();
    expect(apiMocks.getDocument).toHaveBeenCalledOnce();
  });

  it("上传文档后默认保持详情收起", async () => {
    apiMocks.uploadDocument.mockResolvedValue({
      id: "doc-2", filename: "trend.md", content_type: "text/markdown", size_bytes: 10,
      summary: null, status: "processing", error_message: null, processed_at: null,
      created_at: "2026-07-20", chunk_count: 0
    });
    const documents = useDocuments(ref(false), ref(false));
    const input = document.createElement("input");
    Object.defineProperty(input, "files", {
      value: [new File(["Agent trend"], "trend.md", { type: "text/markdown" })]
    });

    await documents.handleDocumentUpload({ target: input } as unknown as Event);

    expect(documents.selectedDocumentId.value).toBeNull();
    expect(documents.selectedDocument.value).toBeNull();
    expect(apiMocks.getDocument).not.toHaveBeenCalled();
  });
});
