<script setup lang="ts">
import { onMounted, ref } from "vue";

import App from "./App.vue";
import { auth, isUsableSession } from "./services/auth";

const ready = ref(false);
const signedIn = ref(false);
const username = ref("");
const password = ref("");
const submitting = ref(false);
const errorMessage = ref("");

async function refreshSession(): Promise<void> {
  const { data } = await auth.getSession();
  signedIn.value = Boolean(data?.session && isUsableSession(data.session));
  ready.value = true;
}

async function signIn(): Promise<void> {
  errorMessage.value = "";
  submitting.value = true;
  try {
    const { data, error } = await auth.signInWithPassword({
      username: username.value.trim(),
      password: password.value
    });
    if (error || !data?.session || !isUsableSession(data.session)) {
      throw new Error(error?.message || "用户名或密码不正确");
    }
    signedIn.value = true;
    password.value = "";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "登录失败，请稍后重试";
  } finally {
    submitting.value = false;
  }
}

async function signOut(): Promise<void> {
  await auth.signOut();
  signedIn.value = false;
  password.value = "";
}

onMounted(refreshSession);
</script>

<template>
  <div v-if="!ready" class="auth-loading" aria-live="polite">正在检查登录状态…</div>

  <template v-else-if="signedIn">
    <button class="signout-button" type="button" @click="signOut">退出演示账号</button>
    <App />
  </template>

  <main v-else class="auth-shell">
    <section class="auth-intro" aria-labelledby="auth-title">
      <p class="auth-kicker">DEEPRESEARCH / PUBLIC DEMO</p>
      <h1 id="auth-title">进入研究工作台</h1>
      <p class="auth-copy">
        此演示环境会调用搜索与大模型服务。登录后，你的研究历史和上传文档只会在当前账号下可见。
      </p>
      <dl class="auth-limits">
        <div><dt>研究额度</dt><dd>每日 10 次</dd></div>
        <div><dt>上传限制</dt><dd>10 MB / 文件</dd></div>
        <div><dt>会话保护</dt><dd>CloudBase Auth</dd></div>
      </dl>
    </section>

    <section class="auth-panel" aria-label="登录表单">
      <div class="auth-rule" aria-hidden="true"></div>
      <p class="auth-label">受控访问</p>
      <form @submit.prevent="signIn">
        <label>
          用户名
          <input
            v-model="username"
            name="username"
            autocomplete="username"
            maxlength="64"
            required
          />
        </label>
        <label>
          密码
          <input
            v-model="password"
            name="password"
            type="password"
            autocomplete="current-password"
            minlength="8"
            required
          />
        </label>
        <p v-if="errorMessage" class="auth-error" role="alert">{{ errorMessage }}</p>
        <button type="submit" :disabled="submitting">
          {{ submitting ? "正在验证…" : "登录并继续" }}
        </button>
      </form>
      <p class="auth-note">演示账号由站点所有者提供，请勿在此输入其他网站的密码。</p>
    </section>
  </main>
</template>

<style scoped>
@import url("https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:wght@600&display=swap");

.auth-loading {
  min-height: 100vh;
  display: grid;
  place-items: center;
  color: #334155;
  background: #f7f5ef;
  font-family: "IBM Plex Sans", sans-serif;
}

.auth-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
  gap: clamp(2rem, 7vw, 8rem);
  align-items: center;
  padding: clamp(2rem, 7vw, 7rem);
  color: #111827;
  background:
    linear-gradient(90deg, rgba(15, 118, 110, 0.08) 1px, transparent 1px) 0 0 / 72px 72px,
    #f7f5ef;
  font-family: "IBM Plex Sans", sans-serif;
}

.auth-intro {
  max-width: 760px;
  align-self: end;
  padding-bottom: 7vh;
}

.auth-kicker,
.auth-label {
  color: #0f766e;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.16em;
}

h1 {
  max-width: 9ch;
  margin: 0.75rem 0 1.25rem;
  font-family: "IBM Plex Serif", serif;
  font-size: clamp(3rem, 7vw, 6.6rem);
  line-height: 0.96;
}

.auth-copy {
  max-width: 58ch;
  color: #475569;
  font-size: 1.04rem;
  line-height: 1.8;
}

.auth-limits {
  display: flex;
  flex-wrap: wrap;
  gap: 1px;
  margin-top: 2.5rem;
  background: #cbd5e1;
  border: 1px solid #cbd5e1;
}

.auth-limits div {
  min-width: 150px;
  flex: 1;
  padding: 1rem;
  background: #f7f5ef;
}

.auth-limits dt {
  color: #64748b;
  font-size: 0.75rem;
}

.auth-limits dd {
  margin: 0.35rem 0 0;
  font-weight: 600;
}

.auth-panel {
  position: relative;
  align-self: start;
  margin-top: 7vh;
  padding: 2.25rem;
  color: #f8fafc;
  background: #111827;
  border-top: 6px solid #0f766e;
}

.auth-rule {
  position: absolute;
  width: 40%;
  height: 1px;
  top: 2.65rem;
  right: -10%;
  background: #cbd5e1;
}

.auth-label {
  margin: 0 0 2.5rem;
}

form {
  display: grid;
  gap: 1.25rem;
}

label {
  display: grid;
  gap: 0.55rem;
  color: #cbd5e1;
  font-size: 0.86rem;
}

input {
  width: 100%;
  box-sizing: border-box;
  padding: 0.85rem 0.9rem;
  color: #f8fafc;
  background: transparent;
  border: 1px solid #64748b;
  border-radius: 0;
  font: inherit;
}

input:focus {
  outline: 2px solid #0f766e;
  outline-offset: 2px;
}

button {
  padding: 0.9rem 1rem;
  color: #f8fafc;
  background: #0f766e;
  border: 0;
  font: 600 0.9rem "IBM Plex Sans", sans-serif;
  cursor: pointer;
}

button:disabled {
  cursor: wait;
  opacity: 0.65;
}

.auth-error {
  margin: 0;
  color: #fecaca;
  font-size: 0.86rem;
}

.auth-note {
  margin: 1.5rem 0 0;
  color: #94a3b8;
  font-size: 0.76rem;
  line-height: 1.6;
}

.signout-button {
  position: fixed;
  z-index: 50;
  top: 1rem;
  right: 1rem;
  padding: 0.65rem 0.85rem;
  border: 1px solid #cbd5e1;
  color: #334155;
  background: rgba(247, 245, 239, 0.94);
}

@media (max-width: 760px) {
  .auth-shell {
    grid-template-columns: 1fr;
    gap: 2rem;
    padding: 2rem 1.25rem;
  }

  .auth-intro,
  .auth-panel {
    align-self: auto;
    margin: 0;
    padding-bottom: 0;
  }

  .auth-panel {
    padding: 1.5rem;
  }

  .auth-rule {
    display: none;
  }

  h1 {
    font-size: clamp(2.8rem, 15vw, 4.5rem);
  }
}
</style>
