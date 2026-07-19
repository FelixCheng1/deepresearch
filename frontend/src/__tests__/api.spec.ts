import { beforeEach, describe, expect, it, vi } from "vitest";

const accessTokenMock = vi.hoisted(() => vi.fn());
vi.mock("../services/auth", () => ({ getAccessToken: accessTokenMock }));

import { AUTH_EXPIRED_EVENT, AuthenticationExpiredError, authenticatedFetch } from "../services/api";

beforeEach(() => {
  accessTokenMock.mockReset();
  vi.unstubAllGlobals();
});

describe("authenticatedFetch", () => {
  it("附加 Bearer Token", async () => {
    accessTokenMock.mockResolvedValue("token-1");
    const fetchMock = vi.fn().mockResolvedValue(new Response("ok", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await authenticatedFetch("https://api.example.test/documents");

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer token-1");
  });

  it("401 只通过统一事件报告认证失效", async () => {
    accessTokenMock.mockResolvedValue("expired-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 401 })));
    const listener = vi.fn();
    window.addEventListener(AUTH_EXPIRED_EVENT, listener);

    await expect(authenticatedFetch("https://api.example.test/documents")).rejects.toBeInstanceOf(AuthenticationExpiredError);
    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener(AUTH_EXPIRED_EVENT, listener);
  });
});
