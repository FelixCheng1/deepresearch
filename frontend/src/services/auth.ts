import cloudbase from "@cloudbase/js-sdk";

const env = import.meta.env.VITE_CLOUDBASE_ENV_ID;
const accessKey = import.meta.env.VITE_CLOUDBASE_PUBLISHABLE_KEY;

if (!env || !accessKey) {
  throw new Error("CloudBase 前端认证配置缺失");
}

const app = cloudbase.init({
  env,
  region: "ap-shanghai",
  accessKey,
  auth: {
    detectSessionInUrl: true
  }
});

export const auth = app.auth({ persistence: "local" });

export function isUsableSession(session: unknown): boolean {
  if (!session || typeof session !== "object") {
    return false;
  }
  const value = session as {
    is_anonymous?: boolean;
    user?: { is_anonymous?: boolean };
  };
  return !value.is_anonymous && !value.user?.is_anonymous;
}

export async function getAccessToken(): Promise<string | null> {
  const { data, error } = await auth.getSession();
  if (error || !data?.session || !isUsableSession(data.session)) {
    return null;
  }
  return data.session.access_token || null;
}
