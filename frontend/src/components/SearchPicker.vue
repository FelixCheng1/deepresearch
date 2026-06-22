<template>
  <label class="field option search-picker">
    <span>搜索引擎</span>
    <button
      type="button"
      class="search-select-button"
      :class="{ open }"
      @click="$emit('update:open', !open)"
    >
      <span>{{ selectedLabel }}</span>
      <span class="search-chevron">⌄</span>
    </button>
    <div v-if="open" class="search-menu">
      <button
        v-for="option in options"
        :key="option.value || 'default'"
        type="button"
        class="search-option"
        :class="{ active: modelValue === option.value }"
        @click="select(option.value)"
      >
        <span class="search-option-name">{{ option.label }}</span>
        <span class="search-option-info" tabindex="0" @click.stop>!</span>
        <span class="search-option-tooltip">{{ option.detail }}</span>
      </button>
    </div>
  </label>
</template>

<script lang="ts" setup>
import type { SearchOptionItem } from "../types";

defineProps<{
  modelValue: string;
  open: boolean;
  selectedLabel: string;
  options: SearchOptionItem[];
}>();

const emit = defineEmits<{
  "update:modelValue": [value: string];
  "update:open": [open: boolean];
}>();

function select(value: string) {
  emit("update:modelValue", value);
  emit("update:open", false);
}
</script>