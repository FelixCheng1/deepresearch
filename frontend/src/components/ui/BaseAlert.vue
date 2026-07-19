<script setup lang="ts">
withDefaults(defineProps<{ tone?: "error" | "success" | "info" }>(), { tone: "info" });
</script>

<template>
  <p class="base-alert" :class="`base-alert--${tone}`" :role="tone === 'error' ? 'alert' : 'status'">
    <slot />
  </p>
</template>
