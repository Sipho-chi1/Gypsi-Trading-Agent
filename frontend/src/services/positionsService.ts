/**
 * Positions — PENDING backend contract.
 *
 * Typed adapter pattern: this service owns the ONLY import point where an
 * eventual FastAPI positions response is mapped into the UI `Position` model.
 * Until the backend exposes positions, every call reports PendingContractError
 * so the UI renders a designed "awaiting backend" state — never fake data.
 *
 * ── INTEGRATION POINT ──────────────────────────────────────────────────
 * When the backend provides positions (e.g. GET /positions), replace the body
 * of `list()` with:
 *
 *   const raw = await apiRequest<unknown>("/positions");
 *   return adaptPositions(raw); // map into Position[] — do NOT invent fields
 * ───────────────────────────────────────────────────────────────────────
 */

import { PendingContractError } from "../types/api";
import type { Position } from "../types/position";

export const positionsService = {
  /** Fetch open positions. Throws PendingContractError until backend contract lands. */
  async list(): Promise<Position[]> {
    throw new PendingContractError("positions");
  },
};
