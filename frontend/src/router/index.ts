import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

import { ensureAuthSession } from "../composables/useAuthSession";

const routes: RouteRecordRaw[] = [
  { path: "/", redirect: "/workspace" },
  { path: "/login", name: "login", component: () => import("../pages/LoginPage.vue"), meta: { guestOnly: true } },
  { path: "/register", name: "register", component: () => import("../pages/RegisterPage.vue"), meta: { guestOnly: true } },
  { path: "/verify-email", name: "verify-email", component: () => import("../pages/VerifyEmailPage.vue"), meta: { guestOnly: true } },
  { path: "/forgot-password", name: "forgot-password", component: () => import("../pages/ForgotPasswordPage.vue"), meta: { guestOnly: true } },
  { path: "/workspace", name: "workspace", component: () => import("../pages/WorkspacePage.vue"), meta: { requiresAuth: true } },
  { path: "/:pathMatch(.*)*", redirect: "/workspace" }
];

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: () => ({ top: 0 })
});

router.beforeEach(async (to) => {
  const signedIn = await ensureAuthSession();
  if (to.meta.requiresAuth && !signedIn) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (to.meta.guestOnly && signedIn) return { name: "workspace" };
  return true;
});
