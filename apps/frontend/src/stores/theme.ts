import { ref, watch } from "vue";
import { defineStore } from "pinia";

const STORAGE_KEY = "super-ai-theme";
type Theme = "light" | "dark";

function storedTheme(): Theme {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === "dark" || raw === "light") return raw;
  } catch {
    // localStorage blocked
  }
  return "light";
}

function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute("data-theme", theme);
}

export const useThemeStore = defineStore("theme", () => {
  const theme = ref<Theme>(storedTheme());

  const isDark = ref(theme.value === "dark");

  function toggle(): void {
    isDark.value = !isDark.value;
    theme.value = isDark.value ? "dark" : "light";
    applyTheme(theme.value);
    try {
      localStorage.setItem(STORAGE_KEY, theme.value);
    } catch {
      // localStorage blocked
    }
  }

  // Watch for external changes (e.g. system preference listener in main.ts)
  watch(theme, (val) => {
    isDark.value = val === "dark";
    applyTheme(val);
  });

  return { theme, isDark, toggle };
});
