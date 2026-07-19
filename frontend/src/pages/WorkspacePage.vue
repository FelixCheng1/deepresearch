<template>
  <main class="app-shell" :class="{ expanded: isExpanded }">
    <header class="workspace-account-bar">
      <span>DEEPRESEARCH / PRIVATE WORKSPACE</span>
      <button type="button" @click="handleSignOut">退出登录</button>
    </header>
    <div class="aurora" aria-hidden="true">
      <span></span>
      <span></span>
      <span></span>
    </div>

    <div v-if="!isExpanded" class="layout layout-centered">
      <ResearchForm
        :topic="form.topic"
        :search-api="form.searchApi"
        :search-menu-open="searchMenuOpen"
        :selected-search-label="selectedSearchLabel"
        :search-option-items="searchOptionItems"
        :loading="loading"
        :error="error"
        @update:topic="form.topic = $event"
        @update:search-api="form.searchApi = $event"
        @update:search-menu-open="searchMenuOpen = $event"
        @submit="handleSubmit"
        @cancel="cancelResearch"
      >
        <template #documents>
          <DocumentLibrary
            variant="home"
            :header-text="documents.length ? `${documents.length} 个文档可检索` : '未上传文档'"
            :dropzone-title="documents.length ? '研究将优先检索这些文档' : '先上传研究文档'"
            :dropzone-hint="documentLoading ? '正在上传并解析...' : '支持 .txt / .md / .pdf / .docx，上传后会后台解析并进入 RAG 检索。'"
            empty-text="暂无文档，仍可直接开始研究。"
            :documents="documents"
            :document-loading="documentLoading"
            :document-detail-loading="documentDetailLoading"
            :document-deleting="documentDeleting"
            :document-retrying="documentRetrying"
            :upload-disabled="uploadDisabled"
            :document-success="documentSuccess"
            :document-error="documentError"
            :selected-document-id="selectedDocumentId"
            :selected-document="selectedDocument"
            :visible-document-chunks="visibleDocumentChunks"
            :expanded-chunk-ids="expandedChunkIds"
            :document-status-text="documentStatusText"
            :document-preview-text="documentPreviewText"
            :preview-text="previewText"
            @upload="handleDocumentUpload"
            @select="selectDocument"
            @retry="handleRetryDocument"
            @delete="handleDeleteDocument"
            @toggle-chunk="toggleChunk"
          />
        </template>
        <template #history>
          <ResearchHistory
            :runs="researchRuns"
            :loading="historyLoading"
            :error="historyError"
            :replaying-run-id="replayingRunId"
            @refresh="refreshResearchRuns"
            @replay="loadResearchRun"
          />
        </template>
      </ResearchForm>
    </div>

    <div v-else class="layout layout-fullscreen">
      <aside class="sidebar">
        <div class="sidebar-header">
          <button class="back-btn" @click="goBack" :disabled="loading">
            <svg viewBox="0 0 24 24" width="20" height="20">
              <path d="M19 12H5M12 19l-7-7 7-7" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            返回
          </button>
          <h2>深度研究助手</h2>
        </div>

        <div class="research-info">
          <div class="info-item">
            <label>研究主题</label>
            <p class="topic-display">{{ form.topic }}</p>
          </div>

          <div class="info-item" v-if="form.searchApi">
            <label>搜索引擎</label>
            <p>{{ form.searchApi }}</p>
          </div>

          <div class="info-item" v-if="totalTasks > 0">
            <label>研究进度</label>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: `${(completedTasks / totalTasks) * 100}%` }"></div>
            </div>
            <p class="progress-text">{{ completedTasks }} / {{ totalTasks }} 任务完成</p>
          </div>

          <div class="info-item document-library">
            <DocumentLibrary
              variant="sidebar"
              :header-text="`本次启动时 ${researchDocumentCount} 个文档可检索`"
              :dropzone-title="documents.length ? `${documents.length} 个文档在库` : '暂无文档'"
              :dropzone-hint="sidebarDocumentHint"
              empty-text="暂无文档"
              :muted="loading"
              :documents="documents"
              :document-loading="documentLoading"
              :document-detail-loading="documentDetailLoading"
              :document-deleting="documentDeleting"
              :document-retrying="documentRetrying"
              :upload-disabled="uploadDisabled"
              :document-success="documentSuccess"
              :document-error="documentError"
              :selected-document-id="selectedDocumentId"
              :selected-document="selectedDocument"
              :visible-document-chunks="visibleDocumentChunks"
              :expanded-chunk-ids="expandedChunkIds"
              :document-status-text="documentStatusText"
              :document-preview-text="documentPreviewText"
              :preview-text="previewText"
              @upload="handleDocumentUpload"
              @select="selectDocument"
              @retry="handleRetryDocument"
              @delete="handleDeleteDocument"
              @toggle-chunk="toggleChunk"
            />
          </div>
        </div>

        <div class="sidebar-actions">
          <button class="new-research-btn" @click="startNewResearch">
            <svg viewBox="0 0 24 24" width="18" height="18">
              <path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>
            </svg>
            开始新研究
          </button>
        </div>
      </aside>

      <section class="panel panel-result">
        <header class="status-bar">
          <div class="status-main">
            <div class="status-chip" :class="{ active: loading }">
              <span class="dot"></span>
              {{ loading ? "研究进行中" : "研究流程完成" }}
            </div>
            <span class="status-meta">
              任务进度：{{ completedTasks }} / {{ totalTasks || todoTasks.length || 1 }}
            </span>
          </div>
        </header>

        <div class="result-workbench">
          <div class="content-column">
            <WorkflowPanel
              :collapsed="workflowCollapsed"
              :completed-workflow-nodes="completedWorkflowNodes"
              :visible-workflow-nodes="visibleWorkflowNodes"
              :workflow-edges="workflowEdges"
              :global-workflow-nodes="globalWorkflowNodes"
              :task-workflow-rows="taskWorkflowRows"
              :report-workflow-nodes="reportWorkflowNodes"
              :selected-workflow-node-id="selectedWorkflowNodeId"
              :format-workflow-status="formatWorkflowStatus"
              @update:collapsed="workflowCollapsed = $event"
              @select-node="selectedWorkflowNodeId = $event"
              @select-task="activeTaskId = $event"
            />

            <TaskSection
              :todo-tasks="todoTasks"
              :active-task-id="activeTaskId"
              :current-task="currentTask"
              :current-task-title="currentTaskTitle"
              :current-task-intent="currentTaskIntent"
              :current-task-query="currentTaskQuery"
              :current-task-note-id="currentTaskNoteId"
              :current-task-note-path="currentTaskNotePath"
              :current-task-summary="currentTaskSummary"
              :summary-highlight="summaryHighlight"
              :format-task-status="formatTaskStatus"
              @update:active-task-id="activeTaskId = $event"
              @copy-note-path="copyNotePath"
            />

            <ReportBlock
              :report-markdown="reportMarkdown"
              :rendered-report-html="renderedReportHtml"
              :report-highlight="reportHighlight"
            />
          </div>

          <EvidenceColumn
            :selected-workflow-node="selectedWorkflowNode"
            :current-task-sources="currentTaskSources"
            :current-task-tool-calls="currentTaskToolCalls"
            :sources-highlight="sourcesHighlight"
            :tool-highlight="toolHighlight"
            :format-workflow-status="formatWorkflowStatus"
            :workflow-task-title="workflowTaskTitle"
            :is-document-source="isDocumentSource"
            :format-tool-parameters="formatToolParameters"
            :format-tool-result="formatToolResult"
            @copy-note-path="copyNotePath"
          />
        </div>
      </section>
    </div>
  </main>
</template>

<script lang="ts" setup>
import { onBeforeUnmount, onMounted } from "vue";
import { useRouter } from "vue-router";

import DocumentLibrary from "../components/DocumentLibrary.vue";
import EvidenceColumn from "../components/EvidenceColumn.vue";
import ReportBlock from "../components/ReportBlock.vue";
import ResearchForm from "../components/ResearchForm.vue";
import ResearchHistory from "../components/ResearchHistory.vue";
import TaskSection from "../components/TaskSection.vue";
import WorkflowPanel from "../components/WorkflowPanel.vue";
import { useAuthSession } from "../composables/useAuthSession";
import { useDocuments } from "../composables/useDocuments";
import { useResearchFlow } from "../composables/useResearchFlow";
import { useResearchHistory } from "../composables/useResearchHistory";
import { useWorkflowState } from "../composables/useWorkflowState";

const router = useRouter();
const authSession = useAuthSession();
const workflow = useWorkflowState();
const research = useResearchFlow(workflow);
const documentLibrary = useDocuments(research.loading, research.isExpanded);
const history = useResearchHistory();

const {
  progressLogs, workflowCollapsed, todoTasks, activeTaskId, reportMarkdown,
  workflowNodes, workflowEdges, selectedWorkflowNodeId, summaryHighlight,
  sourcesHighlight, reportHighlight, toolHighlight, totalTasks, completedTasks,
  visibleWorkflowNodes, completedWorkflowNodes, globalWorkflowNodes,
  reportWorkflowNodes, taskWorkflowRows, selectedWorkflowNode, currentTask,
  currentTaskSources, currentTaskSummary, currentTaskTitle, currentTaskIntent,
  currentTaskQuery, currentTaskNoteId, currentTaskNotePath, currentTaskToolCalls,
  renderedReportHtml, formatTaskStatus, formatWorkflowStatus, workflowTaskTitle,
  copyNotePath, formatToolParameters, formatToolResult, isDocumentSource
} = workflow;

const {
  form, loading, error, isExpanded, searchMenuOpen, researchDocumentCount,
  searchOptionItems, selectedSearchLabel, selectSearchApi, cancelResearch,
  goBack, startNewResearch
} = research;

const {
  documents, documentLoading, documentDetailLoading, documentDeleting,
  documentRetrying, documentError, documentSuccess, selectedDocumentId,
  selectedDocument, expandedChunkIds, visibleDocumentChunks, uploadDisabled,
  sidebarDocumentHint, refreshDocuments, selectDocument, handleRetryDocument,
  handleDeleteDocument, toggleChunk, previewText, documentPreviewText,
  handleDocumentUpload, documentStatusText
} = documentLibrary;

const {
  researchRuns, historyLoading, historyError, replayingRunId,
  refreshResearchRuns
} = history;

async function handleSubmit(): Promise<void> {
  await research.handleSubmit(documents.value.length, refreshResearchRuns);
}

async function loadResearchRun(runId: string): Promise<void> {
  const loaded = await history.loadResearchRun(runId);
  if (!loaded) return;
  workflow.restore(loaded.replay);
  research.restoreContext(loaded.run.topic, loaded.run.search_api ?? "", documents.value.length);
  workflow.addLog(`已恢复历史运行 ${loaded.run.id.slice(0, 8)}`);
}

async function handleSignOut(): Promise<void> {
  research.dispose();
  documentLibrary.dispose();
  workflow.reset();
  await authSession.expire();
  await router.replace("/login");
}

onMounted(() => {
  void refreshDocuments();
  void refreshResearchRuns();
});

onBeforeUnmount(() => {
  research.dispose();
  documentLibrary.dispose();
});
</script>


<style>
.app-shell {
  --bg: var(--paper);
  --surface: var(--paper-raised);
  --surface-soft: #f3f0e8;
  --surface-muted: var(--paper-deep);
  --border: var(--line);
  --border-strong: var(--line-strong);
  --text: var(--ink);
  --muted: var(--slate);
  --subtle: #94a3b8;
  --primary: var(--accent);
  --primary-strong: var(--accent-dark);
  --primary-soft: var(--accent-pale);
  --success: #16a34a;
  --success-soft: #ecfdf5;
  --warning: #ca8a04;
  --warning-soft: #fffbeb;
  --danger: #dc2626;
  --danger-soft: #fef2f2;
  --shadow: var(--shadow-paper);

  position: relative;
  min-height: 100vh;
  padding: 64px 24px;
  display: flex;
  justify-content: center;
  align-items: center;
  background: var(--bg);
  color: var(--text);
  overflow: hidden;
  box-sizing: border-box;
  font-family: var(--font-ui);
}

.workspace-account-bar {
  position: fixed;
  z-index: 40;
  top: 1rem;
  right: 1rem;
  display: flex;
  align-items: center;
  gap: 0.85rem;
  padding: 0.5rem 0.55rem 0.5rem 0.8rem;
  color: var(--muted);
  background: color-mix(in srgb, var(--surface) 94%, transparent);
  border: 1px solid var(--border);
  box-shadow: 0 8px 24px rgba(17, 24, 39, 0.08);
  font: 500 0.68rem var(--font-mono);
  letter-spacing: 0.08em;
}

.workspace-account-bar button {
  padding: 0.45rem 0.65rem;
  color: #fff;
  background: var(--primary);
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font: 600 0.75rem var(--font-ui);
}
.app-shell.expanded {
  padding: 0;
  align-items: stretch;
  overflow: hidden;
}

.aurora {
  display: none;
}

.layout {
  position: relative;
  z-index: 1;
  width: 100%;
  display: flex;
  gap: 24px;
}

.layout-centered {
  max-width: 640px;
  justify-content: center;
  align-items: center;
}

.layout-fullscreen {
  height: 100vh;
  max-width: 100%;
  gap: 0;
  align-items: stretch;
  background: var(--bg);
}

.panel {
  position: relative;
  flex: 1 1 360px;
  padding: 24px;
  border-radius: var(--radius-md);
  background: var(--surface);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
  overflow: hidden;
}

.panel-form {
  max-width: 440px;
}

.panel-centered {
  width: 100%;
  max-width: 640px;
  padding: 40px;
}

.panel-result {
  min-width: 360px;
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.layout-fullscreen .panel-result {
  height: 100vh;
  max-width: none;
  border: 0;
  border-radius: 0;
  box-shadow: none;
  overflow-y: auto;
}

.panel-head {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 28px;
}

.logo {
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
  border-radius: var(--radius-md);
  background: var(--primary);
  box-shadow: 0 10px 24px rgba(15, 118, 110, 0.18);
  flex: 0 0 auto;
}

.logo svg {
  width: 27px;
  height: 27px;
  fill: #ffffff;
}

.panel-form h1,
.sidebar-header h2,
.workflow-panel-header h3,
.tasks-list h3,
.task-header h3,
.report-block h3,
.sources-block h3,
.tools-block h3,
.node-detail-block h3,
.summary-block h3 {
  margin: 0;
  color: var(--text);
  letter-spacing: 0;
}

.panel-form h1 {
  font-size: 28px;
  line-height: 1.15;
  font-weight: 750;
}

.panel-form p {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.6;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.field span,
.info-item label,
.document-library-head label,
.tool-subtitle {
  font-size: 13px;
  font-weight: 650;
  color: #475569;
}

textarea,
input,
select {
  width: 100%;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-strong);
  background: var(--surface);
  color: var(--text);
  font-size: 14px;
  line-height: 1.5;
  transition: border-color 0.16s ease, box-shadow 0.16s ease, background 0.16s ease;
}

textarea {
  min-height: 112px;
  resize: vertical;
  font-family: inherit;
}

textarea:focus,
input:focus,
select:focus,
.search-select-button:focus-visible,
button:focus-visible,
a:focus-visible {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.16);
}

button,
a,
.upload-button {
  touch-action: manipulation;
}

.options {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.option {
  flex: 1;
  min-width: 180px;
}

.search-picker {
  position: relative;
}

.search-select-button {
  width: 100%;
  min-height: 50px;
  padding: 0 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-strong);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  transition: border-color 0.16s ease, box-shadow 0.16s ease, background 0.16s ease;
}

.search-select-button.open,
.search-select-button:hover {
  border-color: var(--primary);
  background: #ffffff;
}

.search-chevron {
  color: var(--muted);
  font-size: 18px;
  line-height: 1;
}

.search-menu {
  position: absolute;
  z-index: 30;
  left: 0;
  right: 0;
  top: calc(100% + 8px);
  padding: 6px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--surface);
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.14);
}

.search-option {
  position: relative;
  width: 100%;
  min-height: 40px;
  padding: 8px 10px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--text);
  font: inherit;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  cursor: pointer;
  text-align: left;
}

.search-option:hover,
.search-option.active {
  background: var(--primary-soft);
  color: var(--primary-strong);
}

.search-option-info {
  width: 18px;
  height: 18px;
  border-radius: 999px;
  border: 1px solid #82c9bf;
  color: var(--primary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 750;
  flex: 0 0 auto;
}

.search-option-tooltip {
  position: absolute;
  right: 8px;
  top: calc(100% + 6px);
  z-index: 40;
  width: min(330px, 80vw);
  padding: 10px 12px;
  border-radius: 12px;
  background: #111827;
  color: #f8fafc;
  font-size: 12px;
  line-height: 1.55;
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.22);
  opacity: 0;
  pointer-events: none;
  transform: translateY(-4px);
  transition: opacity 0.16s ease, transform 0.16s ease;
}

.search-option-info:hover + .search-option-tooltip,
.search-option-info:focus + .search-option-tooltip {
  opacity: 1;
  transform: translateY(0);
}

.form-actions,
.status-bar,
.status-main,
.status-controls,
.task-chip-group,
.document-library-head,
.document-detail-header,
.tool-entry-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.form-actions,
.status-main,
.task-chip-group {
  flex-wrap: wrap;
}

.status-bar,
.document-library-head,
.document-detail-header,
.tool-entry-header {
  justify-content: space-between;
}

.submit,
.secondary-btn,
.back-btn,
.new-research-btn,
.document-delete-btn,
.link-btn,
.chip-action {
  border-radius: 12px;
  font: inherit;
  font-weight: 650;
  cursor: pointer;
  transition: background 0.16s ease, border-color 0.16s ease, color 0.16s ease, box-shadow 0.16s ease;
}

.submit,
.new-research-btn,
.upload-button {
  border: 1px solid var(--primary);
  background: var(--primary);
  color: #ffffff;
}

.submit,
.new-research-btn {
  min-height: 46px;
  padding: 0 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.submit:hover:not(:disabled),
.new-research-btn:hover,
.upload-button:hover:not(.disabled) {
  background: var(--primary-strong);
  border-color: var(--primary-strong);
}

.submit:disabled,
.back-btn:disabled,
.document-delete-btn:disabled,
.upload-button.disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.submit-label {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.spinner {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  animation: spin 1s linear infinite;
}

.secondary-btn,
.back-btn,
.link-btn,
.chip-action {
  border: 1px solid var(--border);
  background: var(--surface);
  color: #334155;
}

.secondary-btn,
.back-btn {
  min-height: 42px;
  padding: 0 14px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.secondary-btn:hover,
.back-btn:hover:not(:disabled),
.link-btn:hover,
.chip-action:hover {
  border-color: var(--border-strong);
  background: var(--surface-muted);
  color: var(--text);
}

.link-btn,
.chip-action {
  min-height: 28px;
  padding: 0 8px;
  font-size: 12px;
}

.error-chip,
.document-message {
  margin: 0;
  padding: 10px 12px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.5;
}

.error-chip,
.document-message.error {
  background: var(--danger-soft);
  border: 1px solid #fecaca;
  color: #991b1b;
}

.error-chip {
  margin-top: 16px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.error-chip svg {
  width: 18px;
  height: 18px;
  fill: currentColor;
}

.document-message.success {
  background: var(--success-soft);
  border: 1px solid #bbf7d0;
  color: #166534;
}

.hint.muted,
.muted,
.muted-text,
.status-meta,
.progress-text,
.task-intent,
.document-empty,
.document-meta,
.document-detail-header span,
.workflow-panel-header p,
.graph-node small,
.tool-subtitle,
.tool-entry-path {
  color: var(--muted);
}

.status-chip,
.task-label,
.task-status,
.tool-entry-note {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: fit-content;
  min-height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
  color: #334155;
  font-size: 12px;
  font-weight: 650;
}

.status-chip.active {
  background: var(--primary-soft);
  border-color: #b9ded8;
  color: var(--primary-strong);
}

.status-chip .dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--primary);
}

.status-chip.active .dot {
  animation: pulse 1.7s ease-in-out infinite;
}

.result-workbench {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 18px;
  align-items: start;
}

.content-column,
.evidence-column {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.evidence-column {
  position: sticky;
  top: 18px;
}

.workflow-panel,
.tasks-list,
.task-detail,
.report-block,
.sources-block,
.tools-block,
.node-detail-block,
.summary-block,
.document-detail-panel,
.home-document-library {
  border: 1px solid var(--border);
  border-radius: 16px;
  background: var(--surface);
}

.workflow-panel,
.task-detail,
.report-block,
.sources-block,
.tools-block,
.node-detail-block,
.summary-block,
.home-document-library {
  padding: 18px;
}

.workflow-panel-header {
  margin-bottom: 14px;
}

.workflow-panel-header h3,
.tasks-list h3,
.task-header h3,
.report-block h3,
.sources-block h3,
.tools-block h3,
.node-detail-block h3,
.summary-block h3 {
  font-size: 16px;
  line-height: 1.35;
}

.workflow-map {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 4px;
}

.workflow-global-row,
.workflow-lane-nodes {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(168px, 1fr));
  gap: 10px;
}

.workflow-global-row.report-row {
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
}

.workflow-lanes {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.workflow-lane {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  gap: 10px;
  align-items: stretch;
}

.workflow-lane-label,
.graph-node,
.task-button,
.document-item-button,
.document-chunk {
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  text-align: left;
  font: inherit;
  transition: background 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
}

.workflow-lane-label {
  border-radius: var(--radius-md);
  padding: 12px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
}

.workflow-lane-label span,
.path-label {
  color: var(--muted);
  font-size: 12px;
}

.workflow-lane-label strong {
  font-size: 13px;
  line-height: 1.35;
}

.graph-node {
  position: relative;
  min-height: 78px;
  border-radius: var(--radius-md);
  padding: 12px;
  display: grid;
  grid-template-columns: 10px 1fr;
  gap: 8px 10px;
  align-items: start;
}

.graph-node:hover,
.graph-node.selected,
.workflow-lane-label:hover,
.task-button:hover,
.document-item-button:hover,
.document-item-button.active,
.document-chunk:hover {
  border-color: #b9ded8;
  background: var(--primary-soft);
}

.graph-node.selected,
.document-item-button.active {
  box-shadow: inset 0 0 0 1px #82c9bf;
}

.graph-node strong,
.graph-node small {
  grid-column: 2;
}

.graph-node strong {
  font-size: 13px;
  line-height: 1.35;
}

.graph-node small {
  font-size: 12px;
  line-height: 1.4;
}

.graph-node.in_progress .graph-node-dot,
.task-status.in_progress,
.task-status.running,
.task-status.processing {
  background: var(--warning-soft);
  border-color: #fde68a;
  color: #92400e;
}

.graph-node.in_progress .graph-node-dot {
  background: var(--warning);
}

.graph-node.completed,
.graph-node.succeeded {
  background: var(--success-soft);
  border-color: #bbf7d0;
}

.graph-node.completed .graph-node-dot,
.graph-node.succeeded .graph-node-dot {
  background: var(--success);
}

.graph-node.failed {
  background: var(--danger-soft);
  border-color: #fecaca;
}

.graph-node.failed .graph-node-dot {
  background: var(--danger);
}

.graph-node.skipped {
  background: var(--surface-muted);
}

.tasks-section {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.tasks-list {
  padding: 16px;
}

.tasks-list ul,
.sources-list,
.tool-list,
.document-list,
.task-notices ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.tasks-list ul,
.sources-list,
.tool-list,
.document-list,
.document-chunks,
.task-notices ul {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.task-button {
  width: 100%;
  border-radius: 12px;
  padding: 12px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.task-title {
  font-size: 13px;
  font-weight: 650;
  line-height: 1.4;
}

.task-status.completed {
  background: var(--success-soft);
  border-color: #bbf7d0;
  color: #166534;
}

.task-status.failed {
  background: var(--danger-soft);
  border-color: #fecaca;
  color: #991b1b;
}

.task-intent {
  margin: 8px 4px 0;
  font-size: 12px;
  line-height: 1.55;
}

.task-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.task-header p {
  margin: 6px 0 0;
  line-height: 1.55;
}

.task-notices {
  padding: 12px;
  margin-bottom: 14px;
  border-radius: 12px;
  border: 1px solid #fde68a;
  background: var(--warning-soft);
}

.task-notices h4 {
  margin: 0 0 8px;
  font-size: 13px;
  color: #92400e;
}

.task-notices li {
  color: #92400e;
  font-size: 12px;
  line-height: 1.5;
}

.block-pre,
.tool-pre {
  margin: 0;
  padding: 14px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
  color: #1f2937;
  font-family: "JetBrains Mono", "Fira Code", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
  overflow: auto;
}

.block-pre {
  max-height: none;
}

.tool-pre {
  max-height: 260px;
}

.summary-block,
.report-block {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.block-highlight {
  animation: highlight 1.1s ease;
}

.node-detail-title {
  margin: 8px 0;
  color: var(--text);
  font-weight: 700;
}

.source-item {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}

.source-item:last-child {
  border-bottom: 0;
}

.source-link {
  color: var(--primary-strong);
  text-decoration: none;
  font-size: 13px;
  font-weight: 650;
  line-height: 1.45;
}

.source-link::after {
  content: " ↗";
  font-size: 11px;
  color: var(--subtle);
}

.source-link:hover {
  color: var(--text);
}

.source-tooltip {
  display: none;
  position: absolute;
  right: 0;
  bottom: calc(100% + 8px);
  z-index: 25;
  width: min(420px, 82vw);
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  box-shadow: 0 18px 38px rgba(15, 23, 42, 0.14);
}

.source-tooltip p {
  margin: 0 0 8px;
  font-size: 12px;
  line-height: 1.55;
}

.source-tooltip p:last-child {
  margin-bottom: 0;
}

.source-item:hover .source-tooltip,
.source-item:focus-within .source-tooltip {
  display: block;
}

.tool-entry {
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tool-entry-title {
  color: var(--text);
  font-size: 13px;
  font-weight: 700;
}

.tool-entry-note {
  background: var(--success-soft);
  border-color: #bbf7d0;
  color: #166534;
}

.tool-entry-path {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
}

.path-text {
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar {
  width: 360px;
  min-width: 360px;
  height: 100vh;
  padding: 28px 22px;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 22px;
  overflow-y: auto;
}

.sidebar-header {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.sidebar-header h2 {
  font-size: 24px;
  line-height: 1.2;
  font-weight: 750;
}

.research-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item p {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: #334155;
}

.topic-display {
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
  color: var(--text) !important;
  font-weight: 650;
}

.progress-bar {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--surface-muted);
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
  background: var(--primary);
  transition: width 0.4s ease;
}

.document-library {
  margin-top: 2px;
}

.home-document-library {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.document-library-head span {
  color: var(--primary-strong);
  font-size: 12px;
  font-weight: 650;
}

.document-dropzone {
  padding: 14px;
  border-radius: var(--radius-md);
  border: 1px dashed var(--border-strong);
  background: var(--surface-soft);
}

.document-dropzone strong {
  display: block;
  margin-bottom: 6px;
  color: var(--text);
  font-size: 14px;
}

.document-dropzone p,
.document-empty,
.document-preview,
.document-chunk p {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
}

.document-dropzone p,
.document-empty {
  color: var(--muted) !important;
}

.upload-button {
  margin-top: 12px;
  width: 100%;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.upload-button input {
  display: none;
}

.document-list li {
  display: flex;
}

.document-item-button {
  width: 100%;
  padding: 11px 12px;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.document-name {
  max-width: 100%;
  color: var(--text);
  font-size: 13px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.document-meta {
  font-size: 12px;
}

.document-detail-panel {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: var(--surface-soft);
}

.document-detail-header div {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.document-detail-header strong {
  color: var(--text);
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.document-detail-header span {
  font-size: 12px;
}

.document-delete-btn {
  flex: 0 0 auto;
  min-height: 32px;
  padding: 0 10px;
  border: 1px solid #fecaca;
  background: var(--danger-soft);
  color: #991b1b;
  font-size: 12px;
}

.document-delete-btn:hover:not(:disabled) {
  background: #fee2e2;
}

.document-preview {
  padding: 10px;
  border-radius: 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: #334155 !important;
  word-break: break-word;
}

.document-chunk {
  width: 100%;
  padding: 10px;
  border-radius: 10px;
}

.document-chunk span {
  display: block;
  margin-bottom: 5px;
  color: var(--primary-strong);
  font-size: 12px;
  font-weight: 700;
}

.document-chunk p {
  color: #334155 !important;
  white-space: pre-wrap;
  word-break: break-word;
}

.sidebar-actions {
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.new-research-btn {
  width: 100%;
}


.workflow-toggle {
  flex: 0 0 auto;
}

.document-meta.processing,
.document-detail-header .processing {
  color: #92400e;
}

.document-meta.ready,
.document-detail-header .ready {
  color: #166534;
}

.document-meta.failed,
.document-detail-header .failed {
  color: #991b1b;
}

.source-headline {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.source-badge {
  flex: 0 0 auto;
  padding: 3px 8px;
  border-radius: 999px;
  background: var(--primary-soft);
  border: 1px solid #b9ded8;
  color: var(--primary-strong);
  font-size: 11px;
  font-weight: 700;
}

.source-item.rag-hit {
  padding: 12px;
  border: 1px solid #b9ded8;
  border-radius: 12px;
  background: var(--primary-soft);
}

.source-snippet {
  margin: 0;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid #dff1ec;
  background: #ffffff;
  color: #334155;
  font-size: 12px;
  line-height: 1.6;
}

.markdown-body {
  padding: 16px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
  color: #1f2937;
  line-height: 1.7;
  font-size: 14px;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 18px 0 10px;
  color: var(--text);
  line-height: 1.35;
}

.markdown-body :deep(h1:first-child),
.markdown-body :deep(h2:first-child),
.markdown-body :deep(h3:first-child) {
  margin-top: 0;
}

.markdown-body :deep(p) {
  margin: 0 0 12px;
}

.markdown-body :deep(ul) {
  margin: 0 0 12px;
  padding-left: 20px;
}

.markdown-body :deep(li) {
  margin: 4px 0;
}

.markdown-body :deep(code) {
  padding: 2px 5px;
  border-radius: 6px;
  background: #e2e8f0;
  font-family: "JetBrains Mono", "Fira Code", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
}

.markdown-body :deep(pre) {
  margin: 0 0 12px;
  padding: 12px;
  overflow: auto;
  border-radius: 10px;
  background: #111827;
  color: #f8fafc;
}

.markdown-body :deep(pre code) {
  padding: 0;
  background: transparent;
  color: inherit;
}

.markdown-body :deep(a) {
  color: var(--primary-strong);
  font-weight: 650;
  text-decoration: none;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 999px;
}

::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.25);
    opacity: 0.58;
  }
}

@keyframes highlight {
  0% {
    border-color: #82c9bf;
    box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.12);
  }
  100% {
    border-color: var(--border);
    box-shadow: none;
  }
}

@media (max-width: 1180px) {
  .result-workbench {
    grid-template-columns: 1fr;
  }

  .evidence-column {
    position: static;
  }
}

@media (max-width: 1024px) {
  .sidebar {
    width: 320px;
    min-width: 320px;
  }

  .tasks-section {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .app-shell {
    padding: 32px 14px;
    overflow: auto;
  }

  .layout,
  .layout-fullscreen {
    flex-direction: column;
  }

  .layout-fullscreen {
    height: auto;
    min-height: 100vh;
  }

  .sidebar {
    width: 100%;
    min-width: 0;
    height: auto;
    max-height: none;
    border-right: 0;
    border-bottom: 1px solid var(--border);
  }

  .layout-fullscreen .panel-result {
    height: auto;
    min-height: 60vh;
  }

  .workflow-lane {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 600px) {
  .panel-centered,
  .panel {
    padding: 22px;
  }

  .panel-head,
  .status-bar,
  .task-header,
  .document-detail-header,
  .tool-entry-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .panel-form h1 {
    font-size: 24px;
  }

  .options,
  .form-actions,
  .status-controls {
    flex-direction: column;
    align-items: stretch;
  }

  .option,
  .submit,
  .secondary-btn {
    width: 100%;
  }

  .workflow-global-row,
  .workflow-global-row.report-row,
  .workflow-lane-nodes {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
  }
}
</style>
