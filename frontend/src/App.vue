<script setup lang="ts">
import { onBeforeUnmount, onMounted } from "vue";
import { RouterView, useRoute, useRouter } from "vue-router";

import BaseSpinner from "./components/ui/BaseSpinner.vue";
import { useAuthSession } from "./composables/useAuthSession";
import { AUTH_EXPIRED_EVENT } from "./services/api";

const route = useRoute();
const router = useRouter();
const session = useAuthSession();
let redirecting = false;

async function handleAuthExpired(): Promise<void> {
  if (redirecting) return;
  redirecting = true;
  const redirect = route.meta.requiresAuth ? route.fullPath : "/workspace";
  try {
    await session.expire();
    await router.replace({ name: "login", query: { redirect, reason: "expired" } });
  } finally {
    redirecting = false;
  }
}

onMounted(() => window.addEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired));
onBeforeUnmount(() => window.removeEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired));
</script>

<template>
  <div v-if="!session.ready" class="app-loading" aria-live="polite">
    <BaseSpinner />
    <span>正在核对研究档案…</span>
  </div>
  <RouterView v-else />
</template>
