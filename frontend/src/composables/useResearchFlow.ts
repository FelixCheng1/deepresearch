import { computed, reactive, ref, type Ref } from "vue";

import { getCapabilities, runResearchStream, type ResearchStreamEvent } from "../services/api";
import type { SearchOptionItem } from "../types";

interface WorkflowPort {
  reportMarkdown: Ref<string>;
  reset: () => void;
  consumeEvent: (event: ResearchStreamEvent, topic: string) => void;
  addLog: (message: string) => void;
}

export function useResearchFlow(workflow: WorkflowPort) {
  const form = reactive({ topic: "", searchApi: "" });
  const loading = ref(false);
  const error = ref("");
  const isExpanded = ref(false);
  const searchMenuOpen = ref(false);
  const researchDocumentCount = ref(0);
  const searchOptionItems = ref<SearchOptionItem[]>([]);
  const capabilitiesLoading = ref(false);
  let controller: AbortController | null = null;

  const selectedSearchLabel = computed(() => {
    if (capabilitiesLoading.value) return "正在读取可用搜索引擎…";
    return searchOptionItems.value.find((item) => item.value === form.searchApi)?.label
      ?? "暂时无法读取搜索能力";
  });

  async function loadCapabilities(): Promise<void> {
    capabilitiesLoading.value = true;
    try {
      const payload = await getCapabilities();
      const options: SearchOptionItem[] = payload.search.engines.map((engine) => ({
        value: engine.id,
        label: engine.label,
        detail: engine.description
      }));
      if (payload.search.default_available) {
        options.unshift({
          value: "",
          label: `沿用后端配置（${payload.search.default_engine}）`,
          detail: `使用后端当前默认的 ${payload.search.default_engine} 搜索。`
        });
      }
      searchOptionItems.value = options;
      if (!options.some((item) => item.value === form.searchApi)) {
        form.searchApi = options[0]?.value ?? "";
      }
      if (options.length) error.value = "";
    } catch (caught) {
      searchOptionItems.value = [];
      error.value = caught instanceof Error ? caught.message : "无法读取可用搜索引擎";
    } finally {
      capabilitiesLoading.value = false;
    }
  }

  function selectSearchApi(value: string): void {
    form.searchApi = value;
    searchMenuOpen.value = false;
  }

  async function handleSubmit(documentCount: number, onSettled: () => void | Promise<void>): Promise<void> {
    if (!form.topic.trim()) {
      error.value = "请输入研究主题";
      return;
    }
    if (!searchOptionItems.value.length) {
      await loadCapabilities();
      if (!searchOptionItems.value.length) {
        error.value = error.value || "当前没有可用的搜索引擎";
        return;
      }
    }
    if (!searchOptionItems.value.some((item) => item.value === form.searchApi)) {
      form.searchApi = searchOptionItems.value[0].value;
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
    form.searchApi = searchOptionItems.value[0]?.value ?? "";
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
    searchOptionItems, capabilitiesLoading, selectedSearchLabel, loadCapabilities,
    selectSearchApi, handleSubmit,
    cancelResearch, goBack, startNewResearch, restoreContext, dispose
  };
}
