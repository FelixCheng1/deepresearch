<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";

import AuthShell from "../components/ui/AuthShell.vue";
import BaseAlert from "../components/ui/BaseAlert.vue";
import BaseButton from "../components/ui/BaseButton.vue";
import BaseField from "../components/ui/BaseField.vue";
import { startEmailRegistration } from "../services/auth";

const router = useRouter();
const email = ref("");
const password = ref("");
const confirmation = ref("");
const submitting = ref(false);
const errorMessage = ref("");

async function handleRegister(): Promise<void> {
  errorMessage.value = "";
  if (password.value !== confirmation.value) {
    errorMessage.value = "两次输入的密码不一致";
    return;
  }
  submitting.value = true;
  try {
    await startEmailRegistration(email.value, password.value);
    await router.push("/verify-email");
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "注册失败，请稍后重试";
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <AuthShell eyebrow="建立档案" title="创建研究账号" description="使用邮箱完成验证。每个账号拥有独立的研究历史、文档库和检索上下文。">
    <form class="auth-form" @submit.prevent="handleRegister">
      <BaseField v-model="email" label="邮箱" name="email" type="email" inputmode="email" autocomplete="email" :maxlength="128" required />
      <BaseField v-model="password" label="密码" name="password" type="password" autocomplete="new-password" :minlength="8" required />
      <BaseField v-model="confirmation" label="确认密码" name="password-confirmation" type="password" autocomplete="new-password" :minlength="8" required />
      <BaseAlert v-if="errorMessage" tone="error">{{ errorMessage }}</BaseAlert>
      <BaseButton type="submit" :loading="submitting">{{ submitting ? "正在发送验证码…" : "注册并验证邮箱" }}</BaseButton>
    </form>
    <p class="auth-footnote">已有账号？<RouterLink to="/login">返回登录</RouterLink></p>
  </AuthShell>
</template>
