/**
 * Theme Manager for Subsea Web App
 * Supports system preference and manual light/dark toggle.
 */

const THEME_KEY = "subsea_theme";

export function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved) {
    setTheme(saved);
  } else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    setTheme("dark");
  } else {
    setTheme("light");
  }

  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (e) => {
    if (!localStorage.getItem(THEME_KEY)) {
      setTheme(e.matches ? "dark" : "light");
    }
  });

  const toggleBtn = document.getElementById("theme-toggle");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme") || "light";
      const next = current === "dark" ? "light" : "dark";
      setTheme(next);
      localStorage.setItem(THEME_KEY, next);
    });
  }
}

export function setTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  const icon = document.getElementById("theme-icon");
  const label = document.getElementById("theme-label");
  if (icon && label) {
    if (theme === "dark") {
      icon.textContent = "☀️";
      label.textContent = "Light";
    } else {
      icon.textContent = "🌙";
      label.textContent = "Dark";
    }
  }
  window.dispatchEvent(new CustomEvent("subsea:themechange", { detail: { theme } }));
}

export function getTheme() {
  return document.documentElement.getAttribute("data-theme") || "light";
}
