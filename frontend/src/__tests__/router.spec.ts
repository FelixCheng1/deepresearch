import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const authState = vi.hoisted(() => ({ signedIn: false }));
vi.mock("../composables/useAuthSession", () => ({
  ensureAuthSession: vi.fn(async () => authState.signedIn)
}));

vi.mock("../services/auth", () => ({
  signIn: vi.fn(),
  startEmailRegistration: vi.fn(),
  verifyPendingEmail: vi.fn(),
  getPendingEmailVerification: vi.fn(() => null),
  getRememberedPendingEmail: vi.fn(() => ""),
  startPasswordReset: vi.fn(),
  completePasswordReset: vi.fn()
}));
import { router } from "../router";

beforeAll(() => vi.stubGlobal("scrollTo", vi.fn()));

beforeEach(async () => {
  authState.signedIn = false;
  await router.replace("/");
});

describe("路由守卫", () => {
  it("访客访问工作台时跳转登录并保留目标地址", async () => {
    await router.push("/workspace");
    expect(router.currentRoute.value.name).toBe("login");
    expect(router.currentRoute.value.query.redirect).toBe("/workspace");
  });

  it("已登录用户访问认证页时回到工作台", async () => {
    authState.signedIn = true;
    await router.push("/register");
    expect(router.currentRoute.value.name).toBe("workspace");
  });
});
