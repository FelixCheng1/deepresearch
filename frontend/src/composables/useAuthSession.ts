import { computed, ref } from "vue";

import { getSession, onAuthStateChange, signOut } from "../services/auth";
import { notifyAuthenticationExpired } from "../services/api";

export type AuthStatus = "loading" | "authenticated" | "guest";

const status = ref<AuthStatus>("loading");
const user = ref<unknown>(null);
let initialized = false;
let initializing: Promise<boolean> | null = null;
let unsubscribe: (() => void) | null = null;

async function refresh(): Promise<boolean> {
  const result = await getSession();
  const authenticated = Boolean(result.session);
  status.value = authenticated ? "authenticated" : "guest";
  user.value = authenticated ? result.user : null;
  return authenticated;
}

export async function ensureAuthSession(): Promise<boolean> {
  if (initializing) return initializing;
  initializing = refresh().finally(() => { initializing = null; });
  return initializing;
}

export function initializeAuthSession(): void {
  if (initialized) return;
  initialized = true;
  void ensureAuthSession();
  unsubscribe = onAuthStateChange((event) => {
    if (event === "SIGNED_OUT") {
      const wasAuthenticated = status.value === "authenticated";
      status.value = "guest";
      user.value = null;
      if (wasAuthenticated) notifyAuthenticationExpired();
    } else if (["SIGNED_IN", "TOKEN_REFRESHED", "USER_UPDATED", "PASSWORD_RECOVERY", "INITIAL_SESSION"].includes(event)) {
      void ensureAuthSession();
    }
  });
}

export async function expireAuthSession(): Promise<void> {
  if (status.value === "guest") return;
  status.value = "guest";
  user.value = null;
  await signOut();
}

export function markAuthenticated(): void {
  status.value = "authenticated";
  void ensureAuthSession();
}

export function disposeAuthSession(): void {
  unsubscribe?.();
  unsubscribe = null;
  initialized = false;
}

export function useAuthSession() {
  return {
    status,
    user,
    ready: computed(() => status.value !== "loading"),
    signedIn: computed(() => status.value === "authenticated"),
    refresh: ensureAuthSession,
    expire: expireAuthSession,
    markAuthenticated
  };
}

