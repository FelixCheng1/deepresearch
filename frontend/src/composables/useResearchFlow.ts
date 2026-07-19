import { computed, reactive, ref, type Ref } from "vue";

import { runResearchStream, type ResearchStreamEvent } from "../services/api";
import type { SearchOptionItem } from "../types";

interface WorkflowPort {
  reportMarkdown: Ref<string>;
  reset: () => void;
  consumeEvent: (event: ResearchStreamEvent, topic: string) => void;
  addLog: (message: string) => void;
}

const SEARCH_OPTIONS: SearchOptionItem[] = [
  { value: "", label: "沿用后端配置", detail: "使用后端 .env 中的默认搜索引擎配置。" },
  { value: "advanced", label: "advanced", detail: "混合多个搜索引擎，返回结构化 JSON；适合需要全面结果的研究。" },
  { value: "duckduckgo", label: "duckduckgo", detail: "无需 API 密钥，免费且无需注册；适合快速体验。" },
  { value: "tavily", label: "tavily", detail: "需要 API 密钥，专为 AI 检索设计；适合生产环境。" },
  { value: "perplexity", label: "perplexity", detail: "需要 API 密钥，返回 AI 总结和来源。" },
  { value: "searxng", label: "searxng", detail: "自建后无需 API 密钥，开源可控。" }
];

export function useResearchFlow(workflow: WorkflowPort) {
  const form = reactive({ topic: "", searchApi: "" });
  const loading = ref(false);
  const error = ref("");
  const isExpanded = ref(false);
  const searchMenuOpen = ref(false);
  const researchDocumentCount = ref(0);
  let controller: AbortController | null = null;

  const searchOptionItems = SEARCH_OPTIONS;
  const selectedSearchLabel = computed(() => SEARCH_OPTIONS.find((item) => item.value === form.searchApi)?.label ?? "沿用后端配置");

  function selectSearchApi(value: string): void {
    form.searchApi = value;
    searchMenuOpen.value = false;
  }

  async function handleSubmit(documentCount: number, onSettled: () => void | Promise<void>): Promise<void> {
    if (!form.topic.trim()) {
      error.value = "请输入研究主题";
      return;
    }
    controller?.abort();
    researchDocumentCount.value = documentCount;
    loading.value = true;
    error.value = "";
    isExpanded.value = true;
    workflow.reset();
    const activeController = new AbortController();
    controller = activeController;
    const topic = form.topic.trim();
    try {
      await runResearchStream(
        { topic, search_api: form.searchApi || undefined },
        (event) => {
          workflow.consumeEvent(event, topic);
          if (event.type === "error") {
            error.value = typeof event.detail === "string" && event.detail.trim() ? event.detail : "研究过程中发生错误";
          }
        },
        { signal: activeController.signal }
      );
      if (!workflow.reportMarkdown.value) workflow.reportMarkdown.value = "暂无生成的报告";
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") {
        workflow.addLog("已取消当前研究任务");
      } else {
        error.value = caught instanceof Error ? caught.message : "请求失败";
      }
    } finally {
      loading.value = false;
      if (controller === activeController) controller = null;
      await onSettled();
    }
  }

  function cancelResearch(): void {
    if (!loading.value || !controller) return;
    workflow.addLog("正在尝试取消当前研究任务…");
    controller.abort();
  }

  function goBack(): void {
    if (!loading.value) isExpanded.value = false;
  }

  function startNewResearch(): void {
    if (loading.value) cancelResearch();
    workflow.reset();
    isExpanded.value = false;
    form.topic = "";
    form.searchApi = "";
    error.value = "";
  }

  function restoreContext(topic: string, searchApi: string, documentCount: number): void {
    form.topic = topic;
    form.searchApi = searchApi;
    researchDocumentCount.value = documentCount;
    error.value = "";
    isExpanded.value = true;
  }

  function dispose(): void {
    controller?.abort();
    controller = null;
  }

  return {
    form, loading, error, isExpanded, searchMenuOpen, researchDocumentCount,
    searchOptionItems, selectedSearchLabel, selectSearchApi, handleSubmit,
    cancelResearch, goBack, startNewResearch, restoreContext, dispose
  };
}
