<template>
  <section class="history-card" aria-labelledby="history-title">
    <header class="history-head">
      <div>
        <p class="history-eyebrow">RESEARCH ARCHIVE</p>
        <h2 id="history-title">研究历史</h2>
      </div>
      <button class="history-refresh" type="button" :disabled="loading" @click="$emit('refresh')">
        {{ loading ? "同步中" : "刷新" }}
      </button>
    </header>

    <p v-if="error" class="history-error">{{ error }}</p>
    <div v-else-if="loading && !runs.length" class="history-empty">正在读取历史运行…</div>
    <div v-else-if="!runs.length" class="history-empty">
      完成一次研究后，可从这里恢复任务、证据和工具调用。
    </div>
    <ol v-else class="history-list">
      <li v-for="run in runs" :key="run.id" class="history-item">
        <span class="history-rail" aria-hidden="true"></span>
        <button
          class="history-run"
          type="button"
          :disabled="Boolean(replayingRunId)"
          @click="$emit('replay', run.id)"
        >
          <span class="history-topic">{{ run.topic }}</span>
          <span class="history-meta">
            <time :datetime="run.created_at">{{ formatRunTime(run.created_at) }}</time>
            <span>{{ run.search_api || "默认搜索" }}</span>
            <code>{{ run.id.slice(0, 8) }}</code>
          </span>
          <span class="history-action">
            {{ replayingRunId === run.id ? "正在恢复" : "打开快照" }}
          </span>
        </button>
      </li>
    </ol>
  </section>
</template>

<script lang="ts" setup>
import type { ResearchRunSummary } from "../services/api";

defineProps<{
  runs: ResearchRunSummary[];
  loading: boolean;
  error: string;
  replayingRunId: string | null;
}>();

defineEmits<{
  refresh: [];
  replay: [runId: string];
}>();

function formatRunTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "时间未知";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}
</script>

<style scoped>
.history-card {
  margin-top: 18px;
  padding: 18px;
  border: 1px solid color-mix(in srgb, var(--border, #dbe3ee) 82%, var(--primary, #0f766e) 18%);
  border-radius: 18px;
  background:
    linear-gradient(135deg, rgba(15, 118, 110, 0.06), transparent 42%),
    var(--surface, #fff);
}

.history-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.history-eyebrow {
  margin: 0 0 3px;
  color: var(--primary, #0f766e);
  font: 700 10px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: 0.16em;
}

.history-head h2 {
  margin: 0;
  font-size: 16px;
  letter-spacing: -0.02em;
}

.history-refresh {
  border: 0;
  padding: 4px 0;
  color: var(--primary, #0f766e);
  background: transparent;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

.history-refresh:disabled {
  opacity: 0.5;
  cursor: wait;
}

.history-list {
  display: grid;
  gap: 2px;
  max-height: 284px;
  margin: 0;
  padding: 0;
  overflow: auto;
  list-style: none;
}

.history-item {
  position: relative;
  padding-left: 18px;
}

.history-rail {
  position: absolute;
  inset: 0 auto 0 4px;
  width: 1px;
  background: var(--accent-pale, #dff1ec);
}

.history-rail::before {
  content: "";
  position: absolute;
  top: 22px;
  left: -3px;
  width: 7px;
  height: 7px;
  border: 2px solid #fff;
  border-radius: 50%;
  background: var(--primary, #0f766e);
  box-shadow: 0 0 0 1px #82c9bf;
}

.history-run {
  position: relative;
  display: grid;
  width: 100%;
  gap: 6px;
  padding: 12px 78px 12px 12px;
  border: 0;
  border-radius: 12px;
  color: inherit;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background 160ms ease, transform 160ms ease;
}

.history-run:hover:not(:disabled),
.history-run:focus-visible {
  outline: none;
  background: rgba(15, 118, 110, 0.08);
  transform: translateX(2px);
}

.history-run:disabled {
  cursor: wait;
  opacity: 0.65;
}

.history-topic {
  overflow: hidden;
  font-size: 13px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 5px 10px;
  color: var(--muted, #64748b);
  font-size: 11px;
}

.history-meta code {
  color: var(--primary, #0f766e);
  font-size: 10px;
}

.history-action {
  position: absolute;
  top: 50%;
  right: 10px;
  color: var(--primary, #0f766e);
  font-size: 11px;
  font-weight: 650;
  transform: translateY(-50%);
}

.history-empty,
.history-error {
  margin: 0;
  padding: 14px;
  border-radius: 12px;
  background: rgba(148, 163, 184, 0.09);
  color: var(--muted, #64748b);
  font-size: 12px;
  line-height: 1.6;
}

.history-error {
  background: rgba(239, 68, 68, 0.08);
  color: #b91c1c;
}

@media (prefers-reduced-motion: reduce) {
  .history-run {
    transition: none;
  }
}
</style>
