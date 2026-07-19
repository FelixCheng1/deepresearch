<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";

import AuthShell from "../components/ui/AuthShell.vue";
import BaseAlert from "../components/ui/BaseAlert.vue";
import BaseButton from "../components/ui/BaseButton.vue";
import BaseField from "../components/ui/BaseField.vue";
import { completePasswordReset, startPasswordReset } from "../services/auth";

const router = useRouter();
const step = ref<"email" | "reset">("email");
const email = ref("");
const code = ref("");
const password = ref("");
const confirmation = ref("");
const submitting = ref(false);
const errorMessage = ref("");

async function sendCode(): Promise<void> {
  errorMessage.value = "";
  submitting.value = true;
  try {
    await startPasswordReset(email.value);
    step.value = "reset";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "验证码发送失败";
  } finally {
    submitting.value = false;
  }
}

async function resetPassword(): Promise<void> {
  errorMessage.value = "";
  if (password.value !== confirmation.value) {
    errorMessage.value = "两次输入的密码不一致";
    return;
  }
  submitting.value = true;
  try {
    await completePasswordReset(code.value, password.value);
    await router.replace({ path: "/login", query: { reset: "success" } });
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "密码重置失败";
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <AuthShell eyebrow="恢复访问" title="重置账号密码" description="先验证注册邮箱，再设置新密码。验证码只用于本次恢复流程。">
    <form v-if="step === 'email'" class="auth-form" @submit.prevent="sendCode">
      <BaseField v-model="email" label="注册邮箱" name="email" type="email" inputmode="email" autocomplete="email" required />
      <BaseAlert v-if="errorMessage" tone="error">{{ errorMessage }}</BaseAlert>
      <BaseButton type="submit" :loading="submitting">{{ submitting ? "正在发送…" : "发送重置验证码" }}</BaseButton>
    </form>
    <form v-else class="auth-form" @submit.prevent="resetPassword">
      <BaseAlert tone="info">验证码已发送至 {{ email }}</BaseAlert>
      <BaseField v-model="code" label="验证码" name="verification-code" inputmode="numeric" autocomplete="one-time-code" required />
      <BaseField v-model="password" label="新密码" name="new-password" type="password" autocomplete="new-password" :minlength="8" required />
      <BaseField v-model="confirmation" label="确认新密码" name="password-confirmation" type="password" autocomplete="new-password" :minlength="8" required />
      <BaseAlert v-if="errorMessage" tone="error">{{ errorMessage }}</BaseAlert>
      <BaseButton type="submit" :loading="submitting">{{ submitting ? "正在更新…" : "更新密码" }}</BaseButton>
    </form>
    <p class="auth-footnote"><RouterLink to="/login">返回登录</RouterLink></p>
  </AuthShell>
</template>
