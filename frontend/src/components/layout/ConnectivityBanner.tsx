import { useState } from "react";
import { AlertTriangle, RefreshCw, X } from "lucide-react";
import { useHealth } from "../../hooks";
import { cn } from "../../lib/cn";

/**
 * Non-blocking connectivity banner shown when `/health` is unreachable.
 * Cached data still renders below; banner never crashes the app.
 */
export function ConnectivityBanner() {
  const health = useHealth();
  const [dismissed, setDismissed] = useState(false);

  const show = !health.isLoading && health.isError && !dismissed;
  if (!show) return null;

  return (
    <div
      role="status"
      className="flex items-center gap-2 border-b border-negative/30 bg-negative/10 px-4 py-2 text-xs text-negative"
    >
      <AlertTriangle aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
      <span className="min-w-0 flex-1 truncate">
        GYPSI backend unreachable. Showing cached data — retrying automatically.
      </span>
      <button
        type="button"
        onClick={() => health.refetch()}
        aria-label="Retry connection"
        className="inline-flex items-center gap-1 rounded-md px-2 py-1 font-medium transition-colors duration-150 hover:bg-negative/15 cursor-pointer"
      >
        <RefreshCw aria-hidden="true" className={cn("h-3 w-3", health.isFetching && "animate-spin")} />
        Retry
      </button>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        aria-label="Dismiss"
        className="rounded p-1 transition-colors duration-150 hover:bg-negative/15 cursor-pointer"
      >
        <X aria-hidden="true" className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
