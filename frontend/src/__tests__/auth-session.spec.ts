import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  callback: null as ((event: string) => void) | null,
  getSession: vi.fn(),
  signOut: vi.fn(),
  notifyExpired: vi.fn(),
  unsubscribe: vi.fn()
}));

vi.mock("../services/auth", () => ({
  getSession: state.getSession,
  signOut: state.signOut,
  onAuthStateChange: vi.fn((callback: (event: string) => void) => {
    state.callback = callback;
    return () => state.unsubscribe();
  })
}));

vi.mock("../services/api", () => ({
  notifyAuthenticationExpired: state.notifyExpired
}));

import {
  disposeAuthSession,
  ensureAuthSession,
  expireAuthSession,
  initializeAuthSession,
  useAuthSession
} from "../composables/useAuthSession";

const session = { access_token: "token", user: { id: "user-1", is_anonymous: false } };

beforeEach(() => {
  disposeAuthSession();
  vi.clearAllMocks();
  state.callback = null;
  state.getSession.mockResolvedValue({ session, user: session.user, error: null });
  state.signOut.mockResolvedValue(undefined);
});

describe("认证会话事件", () => {
  it("SDK 主动登出时触发统一认证失效并清理用户态", async () => {
    initializeAuthSession();
    await ensureAuthSession();

    state.callback?.("SIGNED_OUT");

    expect(useAuthSession().status.value).toBe("guest");
    expect(state.notifyExpired).toHaveBeenCalledOnce();
  });

  it("用户主动退出不会重复触发失效事件", async () => {
    initializeAuthSession();
    await ensureAuthSession();
    state.signOut.mockImplementation(async () => state.callback?.("SIGNED_OUT"));

    await expireAuthSession();

    expect(useAuthSession().status.value).toBe("guest");
    expect(state.notifyExpired).not.toHaveBeenCalled();
  });
});
