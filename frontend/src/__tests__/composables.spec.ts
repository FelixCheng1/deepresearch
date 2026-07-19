import { ref } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
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

beforeEach(() => vi.clearAllMocks());
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

  it("历史 composable 返回回放快照而不直接改写工作流", async () => {
    apiMocks.listResearchRuns.mockResolvedValue([{ id: "run-1", topic: "研究主题", search_api: "", created_at: "2026-07-20" }]);
    apiMocks.getResearchRun.mockResolvedValue(runDetail);
    const history = useResearchHistory();

    await history.refreshResearchRuns();
    const loaded = await history.loadResearchRun("run-1");

    expect(history.researchRuns.value).toHaveLength(1);
    expect(loaded?.replay.reportMarkdown).toBe("# 报告");
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
});
