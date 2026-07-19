import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [vue()],
  define: {
    "import.meta.env.VITE_CLOUDBASE_ENV_ID": JSON.stringify("test-env"),
    "import.meta.env.VITE_CLOUDBASE_PUBLISHABLE_KEY": JSON.stringify("test-key")
  },
  test: {
    environment: "jsdom",
    clearMocks: true,
    restoreMocks: true
  }
});
