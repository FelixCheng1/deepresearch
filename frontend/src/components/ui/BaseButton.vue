<script setup lang="ts">
withDefaults(defineProps<{
  type?: "button" | "submit" | "reset";
  variant?: "primary" | "secondary" | "quiet" | "danger";
  loading?: boolean;
  disabled?: boolean;
}>(), { type: "button", variant: "primary", loading: false, disabled: false });
</script>

<template>
  <button class="base-button" :class="`base-button--${variant}`" :type="type" :disabled="disabled || loading">
    <span v-if="loading" class="base-button__spinner" aria-hidden="true"></span>
    <slot />
  </button>
</template>
