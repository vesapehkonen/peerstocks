// src/hooks/useDarkMode.js
import { useEffect, useState } from "react";

export default function useDarkMode() {
  const [isDark, setIsDark] = useState(() => {
    // prefer persisted setting; fall back to system
    const saved = localStorage.getItem("theme-dark");
    if (saved !== null) return saved === "true";
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
  });

  useEffect(() => {
    const root = document.documentElement;
    if (isDark) root.classList.add("dark");
    else root.classList.remove("dark");
    localStorage.setItem("theme-dark", String(isDark));
  }, [isDark]);

  return { isDark, setIsDark };
}
