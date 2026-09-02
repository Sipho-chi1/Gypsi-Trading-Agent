/**
 * Markets / watchlist — PENDING backend contract.
 *
 * The default watchlist (SPY, QQQ, AAPL, MSFT, NVDA) is a clearly-marked
 * FRONTEND FALLBACK. The service returns `isFallback: true` so the UI never
 * presents it as backend data.
 *
 * ── INTEGRATION POINT ──────────────────────────────────────────────────
 * When the backend provides a watchlist (e.g. GET /watchlist), replace the
 * body of `getWatchlist()` with a real fetch + adapter mapping, and set
 * `isFallback: false`.
 * ───────────────────────────────────────────────────────────────────────
 */

import { FALLBACK_WATCHLIST } from "../types/market";
import type { Watchlist } from "../types/market";

export const marketService = {
  /** Returns the marked frontend fallback watchlist until backend contract lands. */
  async getWatchlist(): Promise<Watchlist> {
    // INTEGRATION POINT: replace with real backend call when available.
    return {
      isFallback: true,
      symbols: FALLBACK_WATCHLIST,
    };
  },
};
