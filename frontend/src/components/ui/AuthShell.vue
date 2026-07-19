<script setup lang="ts">
defineProps<{ eyebrow: string; title: string; description: string }>();
</script>

<template>
  <main class="auth-shell">
    <section class="auth-shell__story" aria-labelledby="auth-page-title">
      <p class="auth-shell__index">DEEPRESEARCH / ACCESS FILE 01</p>
      <h1 id="auth-page-title">{{ title }}</h1>
      <p>{{ description }}</p>
      <dl>
        <div><dt>研究额度</dt><dd>每日 10 次</dd></div>
        <div><dt>资料边界</dt><dd>按账号隔离</dd></div>
        <div><dt>身份系统</dt><dd>CloudBase Auth</dd></div>
      </dl>
    </section>
    <section class="auth-shell__panel">
      <span class="auth-shell__rule" aria-hidden="true"></span>
      <p class="auth-shell__eyebrow">{{ eyebrow }}</p>
      <slot />
    </section>
  </main>
</template>
