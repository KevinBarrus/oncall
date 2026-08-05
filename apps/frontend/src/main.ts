import { createApp } from "vue";
import { createPinia } from "pinia";

import App from "./App.vue";
import { createAppRouter } from "./router";
import { createAuthRouteAccess, useAuthStore } from "./stores/auth";
import { useThemeStore } from "./stores/theme";
import "./styles.css";

const app = createApp(App);
const pinia = createPinia();
app.use(pinia);

// Apply persisted / system theme before mount to avoid flash
const theme = useThemeStore(pinia);
document.documentElement.setAttribute("data-theme", theme.theme);

app.use(createAppRouter(createAuthRouteAccess(useAuthStore(pinia))));
app.mount("#app");
