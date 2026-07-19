import { ref } from "vue";

import { getResearchRun, listResearchRuns, type ResearchRunDetail, type ResearchRunSummary } from "../services/api";
import { buildHistoryReplay, type HistoryReplayState } from "../services/historyReplay";

export interface LoadedResearchRun {
  run: ResearchRunDetail;
  replay: HistoryReplayState;
}

export function useResearchHistory() {
  const researchRuns = ref<ResearchRunSummary[]>([]);
  const historyLoading = ref(false);
  const historyError = ref("");
  const replayingRunId = ref<string | null>(null);

  async function refreshResearchRuns(): Promise<void> {
    historyLoading.value = true;
    historyError.value = "";
    try {
      researchRuns.value = await listResearchRuns(12);
    } catch (error) {
      historyError.value = error instanceof Error ? error.message : "无法读取研究历史";
    } finally {
      historyLoading.value = false;
    }
  }

  async function loadResearchRun(runId: string): Promise<LoadedResearchRun | null> {
    if (replayingRunId.value) return null;
    replayingRunId.value = runId;
    historyError.value = "";
    try {
      const run = await getResearchRun(runId);
      return { run, replay: buildHistoryReplay(run) };
    } catch (error) {
      historyError.value = error instanceof Error ? error.message : "无法恢复研究历史";
      return null;
    } finally {
      replayingRunId.value = null;
    }
  }

  return { researchRuns, historyLoading, historyError, replayingRunId, refreshResearchRuns, loadResearchRun };
}
