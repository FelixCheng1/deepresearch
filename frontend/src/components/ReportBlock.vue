<template>
  <section
    v-if="reportMarkdown"
    class="report-block report-block-main"
    :class="{ 'block-highlight': reportHighlight }"
  >
    <h3>最终报告</h3>
    <div class="markdown-body" v-html="renderedReportHtml"></div>
  </section>
</template>

<script lang="ts" setup>
defineProps<{
  reportMarkdown: string;
  renderedReportHtml: string;
  reportHighlight: boolean;
}>();
</script>