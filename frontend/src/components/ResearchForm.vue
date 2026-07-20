<template>
  <section class="panel panel-form panel-centered">
    <header class="panel-head">
      <div class="logo">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M12 2.5c-.7 0-1.4.2-2 .6L4.6 7C3.6 7.6 3 8.7 3 9.9v4.2c0 1.2.6 2.3 1.6 2.9l5.4 3.9c1.2.8 2.8.8 4 0l5.4-3.9c1-.7 1.6-1.7 1.6-2.9V9.9c0-1.2-.6-2.3-1.6-2.9L14 3.1a3.6 3.6 0 0 0-2-.6Z"
          />
        </svg>
      </div>
      <div>
        <h1>深度研究助手</h1>
        <p>结合多轮智能检索与总结，实时呈现洞见与引用。</p>
      </div>
    </header>

    <form class="form" @submit.prevent="$emit('submit')">
      <label class="field">
        <span>研究主题</span>
        <textarea
          :value="topic"
          placeholder="例如：2026 年人工智能 Agent 的主要技术趋势"
          rows="4"
          required
          @input="$emit('update:topic', ($event.target as HTMLTextAreaElement).value)"
        ></textarea>
      </label>

      <section class="options">
        <SearchPicker
          :model-value="searchApi"
          :open="searchMenuOpen"
          :selected-label="selectedSearchLabel"
          :options="searchOptionItems"
          @update:model-value="$emit('update:searchApi', $event)"
          @update:open="$emit('update:searchMenuOpen', $event)"
        />
      </section>

      <slot name="documents"></slot>
      <slot name="history"></slot>

      <div class="form-actions">
        <button class="submit" type="submit" :disabled="loading">
          <span class="submit-label">
            <svg
              v-if="loading"
              class="spinner"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="9" stroke-width="3" />
            </svg>
            {{ loading ? "研究进行中..." : "开始研究" }}
          </span>
        </button>
        <button
          v-if="loading"
          type="button"
          class="secondary-btn"
          @click="$emit('cancel')"
        >
          取消研究
        </button>
      </div>
    </form>

    <p v-if="error" class="error-chip">
      <svg viewBox="0 0 20 20" aria-hidden="true">
        <path
          d="M10 3.2c-.3 0-.6.2-.8.5L3.4 15c-.4.7.1 1.6.8 1.6h11.6c.7 0 1.2-.9.8-1.6L10.8 3.7c-.2-.3-.5-.5-.8-.5Zm0 4.3c.4 0 .7.3.7.7v4c0 .4-.3.7-.7.7s-.7-.3-.7-.7V8.2c0-.4.3-.7.7-.7Zm0 6.6a1 1 0 1 1 0 2 1 1 0 0 1 0-2Z"
        />
      </svg>
      {{ error }}
    </p>
    <p v-else-if="loading" class="hint muted">
      正在收集线索与证据，实时进展见右侧区域。
    </p>
  </section>
</template>

<script lang="ts" setup>
import SearchPicker from "./SearchPicker.vue";
import type { SearchOptionItem } from "../types";

defineProps<{
  topic: string;
  searchApi: string;
  searchMenuOpen: boolean;
  selectedSearchLabel: string;
  searchOptionItems: SearchOptionItem[];
  loading: boolean;
  error: string;
}>();

defineEmits<{
  "update:topic": [value: string];
  "update:searchApi": [value: string];
  "update:searchMenuOpen": [value: boolean];
  submit: [];
  cancel: [];
}>();
</script>
