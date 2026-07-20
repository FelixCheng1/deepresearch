<template>
  <div class="tasks-section" v-if="todoTasks.length">
    <aside class="tasks-list">
      <h3>任务清单</h3>
      <ul>
        <li
          v-for="task in todoTasks"
          :key="task.id"
          :class="['task-item', { active: task.id === activeTaskId, completed: task.status === 'completed' }]"
        >
          <button
            type="button"
            class="task-button"
            @click="$emit('update:activeTaskId', task.id)"
          >
            <span class="task-title">{{ task.title }}</span>
            <span class="task-status" :class="task.status">
              {{ formatTaskStatus(task.status) }}
            </span>
          </button>
          <p class="task-intent">{{ task.intent }}</p>
        </li>
      </ul>
    </aside>

    <article class="task-detail" v-if="currentTask">
      <header class="task-header">
        <div>
          <h3>{{ currentTaskTitle || "当前任务" }}</h3>
          <p class="muted" v-if="currentTaskIntent">
            {{ currentTaskIntent }}
          </p>
        </div>
        <div class="task-chip-group">
          <span class="task-label">查询：{{ currentTaskQuery || "" }}</span>
          <span
            v-if="currentTaskNoteId"
            class="task-label note-chip"
            :title="currentTaskNoteId"
          >
            笔记：{{ currentTaskNoteId }}
          </span>
          <span
            v-if="currentTaskNotePath"
            class="task-label note-chip path-chip"
            :title="currentTaskNotePath"
          >
            <span class="path-label">路径：</span>
            <span class="path-text">{{ currentTaskNotePath }}</span>
            <button
              class="chip-action"
              type="button"
              @click="$emit('copy-note-path', currentTaskNotePath)"
            >
              复制
            </button>
          </span>
        </div>
      </header>

      <section v-if="currentTask && currentTask.notices.length" class="task-notices">
        <h4>系统提示</h4>
        <ul>
          <li v-for="(notice, idx) in currentTask.notices" :key="`${notice}-${idx}`">
            {{ notice }}
          </li>
        </ul>
      </section>

      <section v-if="currentTask.searchExecution" class="search-execution">
        <div>
          <span>请求后端</span>
          <strong>{{ currentTask.searchExecution.requestedBackend }}</strong>
        </div>
        <div>
          <span>实际使用的后端</span>
          <strong>{{ currentTask.searchExecution.actualBackend }}</strong>
        </div>
        <p v-if="currentTask.searchExecution.fallbackReason">
          <strong>降级原因：</strong>{{ currentTask.searchExecution.fallbackReason }}
        </p>
        <p v-else class="search-execution-ok">本次未发生搜索后端降级。</p>
      </section>

      <section
        class="summary-block"
        :class="{ 'block-highlight': summaryHighlight }"
      >
        <h3>任务总结</h3>
        <pre class="block-pre">{{ currentTaskSummary || "暂无可用信息" }}</pre>
      </section>
    </article>

    <article class="task-detail" v-else>
      <p class="muted">等待任务规划或执行结果。</p>
    </article>
  </div>
</template>

<script lang="ts" setup>
import type { TodoTaskView } from "../types";

defineProps<{
  todoTasks: TodoTaskView[];
  activeTaskId: number | null;
  currentTask: TodoTaskView | null;
  currentTaskTitle: string;
  currentTaskIntent: string;
  currentTaskQuery: string;
  currentTaskNoteId: string;
  currentTaskNotePath: string;
  currentTaskSummary: string;
  summaryHighlight: boolean;
  formatTaskStatus: (status: string) => string;
}>();

defineEmits<{
  "update:activeTaskId": [taskId: number];
  "copy-note-path": [path: string];
}>();
</script>
