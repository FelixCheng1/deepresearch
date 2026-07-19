<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import AuthShell from "../components/ui/AuthShell.vue";
import BaseAlert from "../components/ui/BaseAlert.vue";
import BaseButton from "../components/ui/BaseButton.vue";
import BaseField from "../components/ui/BaseField.vue";
import { useAuthSession } from "../composables/useAuthSession";
import { getPendingEmailVerification, getRememberedPendingEmail, verifyPendingEmail } from "../services/auth";

const router = useRouter();
const session = useAuthSession();
const code = ref("");
const submitting = ref(false);
const errorMessage = ref("");
const pending = getPendingEmailVerification();
const email = computed(() => pending?.email || getRememberedPendingEmail());
const canVerify = computed(() => Boolean(pending));

async function handleVerify(): Promise<void> {
  errorMessage.value = "";
  submitting.value = true;
  try {
    await verifyPendingEmail(code.value);
    session.markAuthenticated();
    await router.replace("/workspace");
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "邮箱验证失败";
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <AuthShell eyebrow="验证身份" title="查收邮箱验证码" :description="email ? `验证码已发送至 ${email}` : '当前没有待验证的邮箱。'">
    <form v-if="canVerify" class="auth-form" @submit.prevent="handleVerify">
      <BaseField v-model="code" label="验证码" name="verification-code" inputmode="numeric" autocomplete="one-time-code" :maxlength="12" required />
      <BaseAlert v-if="errorMessage" tone="error">{{ errorMessage }}</BaseAlert>
      <BaseButton type="submit" :loading="submitting">{{ submitting ? "正在验证…" : "完成邮箱验证" }}</BaseButton>
    </form>
    <template v-else>
      <BaseAlert tone="error">验证会话已失效。出于安全考虑，密码不会保存在浏览器中。</BaseAlert>
      <RouterLink class="auth-primary-link" to="/register">返回注册并重新发送</RouterLink>
    </template>
    <p class="auth-footnote"><RouterLink to="/login">返回登录</RouterLink></p>
  </AuthShell>
</template>
