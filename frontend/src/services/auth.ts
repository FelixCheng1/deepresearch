import cloudbase from "@cloudbase/js-sdk";

const env = import.meta.env.VITE_CLOUDBASE_ENV_ID;
const accessKey = import.meta.env.VITE_CLOUDBASE_PUBLISHABLE_KEY;

if (!env || !accessKey) throw new Error("CloudBase 前端认证配置缺失");

const app = cloudbase.init({
  env,
  region: "ap-shanghai",
  accessKey,
  auth: { detectSessionInUrl: true }
});

export const auth = app.auth({ persistence: "local" });

type AuthErrorLike = { message?: string };
type AuthResult = { data?: { session?: unknown; user?: unknown }; error?: AuthErrorLike | null };
type VerifyOtp = (params: { token: string; messageId?: string }) => Promise<AuthResult>;
type UpdatePassword = (params: { nonce: string; password: string }) => Promise<AuthResult>;

export interface PendingEmailVerification {
  email: string;
  createdAt: number;
}

let pendingVerification: (PendingEmailVerification & { verifyOtp: VerifyOtp }) | null = null;
let pendingPasswordReset: { email: string; updateUser: UpdatePassword } | null = null;

function operationError(error: AuthErrorLike | null | undefined, fallback: string): Error {
  return new Error(error?.message || fallback);
}

export function isUsableSession(session: unknown): boolean {
  if (!session || typeof session !== "object") return false;
  const value = session as { is_anonymous?: boolean; user?: { is_anonymous?: boolean } };
  return !value.is_anonymous && !value.user?.is_anonymous;
}

export async function getSession() {
  const result = await auth.getSession();
  const session = result.data?.session;
  return {
    session: session && isUsableSession(session) ? session : null,
    user: session && isUsableSession(session) ? result.data?.user ?? session.user : null,
    error: result.error
  };
}

export async function getAccessToken(): Promise<string | null> {
  const { session } = await getSession();
  if (!session || typeof session !== "object") return null;
  const token = (session as { access_token?: unknown }).access_token;
  return typeof token === "string" && token ? token : null;
}

export async function signIn(identifier: string, password: string): Promise<void> {
  const account = identifier.trim();
  const result = account.includes("@")
    ? await auth.signInWithPassword({ email: account, password })
    : await auth.signInWithPassword({ username: account, password });
  if (result.error || !result.data?.session || !isUsableSession(result.data.session)) {
    throw operationError(result.error, "账号或密码不正确");
  }
}

export async function startEmailRegistration(email: string, password: string): Promise<PendingEmailVerification> {
  const normalizedEmail = email.trim().toLowerCase();
  const result = await auth.signUp({ email: normalizedEmail, password });
  if (result.error || !result.data?.verifyOtp) {
    throw operationError(result.error, "注册验证码发送失败");
  }
  pendingVerification = {
    email: normalizedEmail,
    createdAt: Date.now(),
    verifyOtp: result.data.verifyOtp as VerifyOtp
  };
  sessionStorage.setItem("deepresearch:pending-email", normalizedEmail);
  return { email: normalizedEmail, createdAt: pendingVerification.createdAt };
}

export function getPendingEmailVerification(): PendingEmailVerification | null {
  return pendingVerification
    ? { email: pendingVerification.email, createdAt: pendingVerification.createdAt }
    : null;
}

export function getRememberedPendingEmail(): string {
  return sessionStorage.getItem("deepresearch:pending-email") || "";
}

export async function verifyPendingEmail(token: string): Promise<void> {
  if (!pendingVerification) throw new Error("验证会话已失效，请返回注册页重新发送验证码");
  const result = await pendingVerification.verifyOtp({ token: token.trim() });
  if (result.error || !result.data?.session || !isUsableSession(result.data.session)) {
    throw operationError(result.error, "邮箱验证失败");
  }
  pendingVerification = null;
  sessionStorage.removeItem("deepresearch:pending-email");
}

export async function startPasswordReset(email: string): Promise<void> {
  const normalizedEmail = email.trim().toLowerCase();
  const result = await auth.resetPasswordForEmail(normalizedEmail);
  if (result.error || !result.data?.updateUser) {
    throw operationError(result.error, "重置验证码发送失败");
  }
  pendingPasswordReset = {
    email: normalizedEmail,
    updateUser: result.data.updateUser as UpdatePassword
  };
}

export async function completePasswordReset(code: string, password: string): Promise<void> {
  if (!pendingPasswordReset) throw new Error("重置会话已失效，请重新发送验证码");
  const result = await pendingPasswordReset.updateUser({ nonce: code.trim(), password });
  if (result.error) throw operationError(result.error, "密码重置失败");
  pendingPasswordReset = null;
  await auth.signOut();
}

export async function signOut(): Promise<void> {
  pendingVerification = null;
  pendingPasswordReset = null;
  sessionStorage.removeItem("deepresearch:pending-email");
  await auth.signOut();
}

export function onAuthStateChange(callback: (event: string) => void): () => void {
  const result = auth.onAuthStateChange((event: unknown) => callback(String(event)));
  return () => result.data.subscription.unsubscribe();
}
