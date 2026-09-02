/**
 * Confirmed contract: `GET /trades?limit=` -> `TradeOut[]`.
 */

import { apiRequest } from "./apiClient";
import type { Trade } from "../types/trade";

export const tradesService = {
  /** Fetch trades. `limit` is optional (confirmed query param). */
  list(limit?: number): Promise<Trade[]> {
    return apiRequest<Trade[]>("/trades", {
      query: { limit },
    });
  },

  /**
   * Resolve a single trade client-side from the list.
   *
   * NOTE: `GET /trades/{id}` is NOT part of the confirmed contract, so we do
   * not invent it. The Trade Detail page looks up by id from the trades list.
   */
  findById(trades: Trade[], id: number | string): Trade | undefined {
    const numeric = typeof id === "string" ? Number(id) : id;
    if (Number.isNaN(numeric)) return undefined;
    return trades.find((t) => t.id === numeric);
  },
};
