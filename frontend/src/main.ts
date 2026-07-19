import { createApp } from "vue";

import "@fontsource/ibm-plex-sans/latin-400.css";
import "@fontsource/ibm-plex-sans/latin-500.css";
import "@fontsource/ibm-plex-sans/latin-600.css";
import "@fontsource/ibm-plex-serif/latin-600.css";
import "@fontsource/jetbrains-mono/latin-500.css";
import App from "./App.vue";
import { initializeAuthSession } from "./composables/useAuthSession";
import { router } from "./router";
import "./styles/tokens.css";
import "./styles/base.css";
import "./style.css";

initializeAuthSession();
createApp(App).use(router).mount("#app");
