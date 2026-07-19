import { beforeEach, describe, expect, it, vi } from "vitest";

const authMock = vi.hoisted(() => ({
  getSession: vi.fn(),
  signInWithPassword: vi.fn(),
  signUp: vi.fn(),
  resetPasswordForEmail: vi.fn(),
  signOut: vi.fn(),
  onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } }))
}));

vi.mock("@cloudbase/js-sdk", () => ({
  default: { init: () => ({ auth: () => authMock }) }
}));

import {
  completePasswordReset,
  getPendingEmailVerification,
  signIn,
  signOut,
  startEmailRegistration,
  startPasswordReset,
  verifyPendingEmail
} from "../services/auth";

const session = { access_token: "token", user: { id: "user-1", is_anonymous: false } };

beforeEach(async () => {
  vi.clearAllMocks();
  sessionStorage.clear();
  authMock.signOut.mockResolvedValue(undefined);
  await signOut();
});

describe("CloudBase 认证服务", () => {
  it("邮箱和旧用户名分别使用正确的密码登录参数", async () => {
    authMock.signInWithPassword.mockResolvedValue({ data: { session }, error: null });

    await signIn("reader@example.com", "password123");
    await signIn("legacy-user", "password123");

    expect(authMock.signInWithPassword).toHaveBeenNthCalledWith(1, { email: "reader@example.com", password: "password123" });
    expect(authMock.signInWithPassword).toHaveBeenNthCalledWith(2, { username: "legacy-user", password: "password123" });
  });

  it("注册只在内存保存验证句柄，验证后清理上下文", async () => {
    const verifyOtp = vi.fn().mockResolvedValue({ data: { session }, error: null });
    authMock.signUp.mockResolvedValue({ data: { verifyOtp }, error: null });

    await startEmailRegistration("New@Example.com", "password123");
    expect(getPendingEmailVerification()?.email).toBe("new@example.com");
    expect(sessionStorage.getItem("deepresearch:pending-email")).toBe("new@example.com");

    await verifyPendingEmail("123456");
    expect(verifyOtp).toHaveBeenCalledWith({ token: "123456" });
    expect(getPendingEmailVerification()).toBeNull();
  });

  it("没有注册验证上下文时明确拒绝验证码", async () => {
    await expect(verifyPendingEmail("123456")).rejects.toThrow("验证会话已失效");
  });

  it("完成验证码重置密码后退出自动登录会话", async () => {
    const updateUser = vi.fn().mockResolvedValue({ data: { session }, error: null });
    authMock.resetPasswordForEmail.mockResolvedValue({ data: { updateUser }, error: null });

    await startPasswordReset("reader@example.com");
    await completePasswordReset("654321", "new-password123");

    expect(updateUser).toHaveBeenCalledWith({ nonce: "654321", password: "new-password123" });
    expect(authMock.signOut).toHaveBeenCalled();
  });
});
