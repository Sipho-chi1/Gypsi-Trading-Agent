/**
 * ThemeProvider — applies the persisted theme as a `data-theme` attribute on
 * the app root so the CSS variables in index.css switch dark/light globally.
 */

import { useEffect, type ReactNode } from "react";
import { useThemeStore } from "../store/useThemeStore";

export function ThemeProvider({ children }: { children: ReactNode }) {
  const theme = useThemeStore((s) => s.theme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  // Apply immediately (before first paint of the effect) to avoid flash.
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, []);

  return <>{children}</>;
}
