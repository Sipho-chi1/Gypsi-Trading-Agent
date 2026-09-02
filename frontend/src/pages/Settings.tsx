import { useThemeStore } from "../store/useThemeStore";
import { API_BASE_URL } from "../services/apiClient";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardHeader } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { FALLBACK_WATCHLIST } from "../types/market";

export default function Settings() {
  const theme = useThemeStore((s) => s.theme);
  const setTheme = useThemeStore((s) => s.setTheme);
  const isDark = theme === "dark";

  return (
    <div>
      <PageHeader title="Settings" description="Client preferences and configuration." />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-4">
          <CardHeader title="Appearance" subtitle="GYPSI ships in black + yellow (dark) and white + blue (light)." />
          <div className="mt-4 flex gap-2">
            <Button
              variant={isDark ? "primary" : "secondary"}
              onClick={() => setTheme("dark")}
              aria-pressed={isDark}
            >
              Dark
            </Button>
            <Button
              variant={!isDark ? "primary" : "secondary"}
              onClick={() => setTheme("light")}
              aria-pressed={!isDark}
            >
              Light
            </Button>
          </div>
        </Card>

        <Card className="p-4">
          <CardHeader title="API" subtitle="The backend is the single source of truth." />
          <dl className="mt-4 space-y-2 text-sm">
            <div className="flex items-center justify-between gap-3">
              <dt className="text-muted">Base URL</dt>
              <dd className="tabular font-mono text-xs text-foreground">{API_BASE_URL}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-muted">Env var</dt>
              <dd className="tabular font-mono text-xs text-foreground">VITE_API_URL</dd>
            </div>
          </dl>
        </Card>

        <Card className="p-4">
          <CardHeader
            title="Watchlist"
            subtitle="Frontend fallback until the backend watchlist endpoint exists."
          />
          <ul className="mt-3 flex flex-wrap gap-2">
            {FALLBACK_WATCHLIST.map((s) => (
              <li
                key={s.symbol}
                className="rounded-pill border border-border bg-surface px-2.5 py-1 text-xs font-medium text-foreground"
              >
                {s.symbol}
              </li>
            ))}
          </ul>
        </Card>

        <Card className="p-4">
          <CardHeader title="About" subtitle="GYPSI — AI trading agent command center." />
          <p className="mt-3 text-sm leading-6 text-muted">
            GYPSI is a pure client of the GYPSI FastAPI backend. It executes no
            trading, holds no data of its own, and never fabricates results.
          </p>
        </Card>
      </div>
    </div>
  );
}
