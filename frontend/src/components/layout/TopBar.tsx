import { Menu, Moon, Sun } from "lucide-react";
import { useAgentStatus } from "../../hooks";
import { useThemeStore } from "../../store/useThemeStore";
import { useUiStore } from "../../store/useUiStore";
import { AgentStatusIndicator } from "../agent/AgentStatusIndicator";

/**
 * Top bar: mobile menu trigger, GYPSI identity, live agent state,
 * theme toggle. Agent state derived from the ~5s polled status.
 */
export function TopBar() {
  const theme = useThemeStore((s) => s.theme);
  const toggleTheme = useThemeStore((s) => s.toggleTheme);
  const setMobileNavOpen = useUiStore((s) => s.setMobileNavOpen);
  const status = useAgentStatus();
  const state = status.data?.state ?? "UNKNOWN";
  const isDark = theme === "dark";

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/85 px-4 backdrop-blur-md">
      {/* Mobile menu trigger */}
      <button
        type="button"
        onClick={() => setMobileNavOpen(true)}
        aria-label="Open navigation"
        className="inline-flex h-9 w-9 items-center justify-center rounded-md text-muted transition-colors duration-150 hover:bg-surface hover:text-foreground md:hidden"
      >
        <Menu aria-hidden="true" className="h-5 w-5" />
      </button>

      <div className="flex items-center gap-2">
        <img
          src="/gypsi-mark.svg"
          alt=""
          className="h-6 w-6"
          width={24}
          height={24}
        />
        <span className="hidden text-sm font-bold tracking-[0.22em] text-foreground sm:inline">
          GYPSI
        </span>
      </div>

      <div className="ml-auto flex items-center gap-3">
        <AgentStatusIndicator state={state} className="rounded-pill border border-border bg-surface px-2.5 py-1" />
        <button
          type="button"
          onClick={toggleTheme}
          aria-pressed={isDark}
          aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
          className="inline-flex h-9 w-9 items-center justify-center rounded-md text-muted transition-colors duration-150 hover:bg-surface hover:text-foreground"
        >
          {isDark ? (
            <Sun aria-hidden="true" className="h-[18px] w-[18px]" />
          ) : (
            <Moon aria-hidden="true" className="h-[18px] w-[18px]" />
          )}
        </button>
      </div>
    </header>
  );
}
