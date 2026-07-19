<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import AuthShell from "../components/ui/AuthShell.vue";
import BaseAlert from "../components/ui/BaseAlert.vue";
import BaseButton from "../components/ui/BaseButton.vue";
import BaseField from "../components/ui/BaseField.vue";
import { useAuthSession } from "../composables/useAuthSession";
import { signIn } from "../services/auth";

const route = useRoute();
const router = useRouter();
const session = useAuthSession();
const identifier = ref("");
const password = ref("");
const submitting = ref(false);
const errorMessage = ref("");

function safeRedirect(): string {
  const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/workspace";
  return redirect.startsWith("/") && !redirect.startsWith("//") ? redirect : "/workspace";
}

async function handleLogin(): Promise<void> {
  errorMessage.value = "";
  submitting.value = true;
  try {
    await signIn(identifier.value, password.value);
    session.markAuthenticated();
    password.value = "";
    await router.replace(safeRedirect());
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "登录失败，请稍后重试";
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <AuthShell eyebrow="受控访问" title="进入研究工作台" description="登录后，研究历史与上传文档只会在当前账号下可见。旧用户名账号仍可继续使用。">
    <form class="auth-form" @submit.prevent="handleLogin">
      <BaseAlert v-if="route.query.reason === 'expired'" tone="info">登录状态已失效，请重新验证身份。</BaseAlert>
      <BaseAlert v-if="route.query.reset === 'success'" tone="success">密码已更新，请使用新密码登录。</BaseAlert>
      <BaseField v-model="identifier" label="邮箱或用户名" name="identifier" autocomplete="username" :maxlength="128" required />
      <BaseField v-model="password" label="密码" name="password" type="password" autocomplete="current-password" :minlength="8" required />
      <BaseAlert v-if="errorMessage" tone="error">{{ errorMessage }}</BaseAlert>
      <BaseButton type="submit" :loading="submitting">{{ submitting ? "正在验证…" : "登录并继续" }}</BaseButton>
    </form>
    <nav class="auth-links" aria-label="账号操作">
      <RouterLink to="/register">注册新账号</RouterLink>
      <RouterLink to="/forgot-password">忘记密码</RouterLink>
    </nav>
  </AuthShell>
</template>
