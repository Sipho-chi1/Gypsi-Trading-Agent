/**
 * Round Table — PENDING backend contract.
 *
 * Typed adapter pattern. The UI renders a fixed set of perspective panels
 * (Market → Technical → Risk → Sentiment → Macro → Execution → Consensus →
 * Final Verdict). Until the backend provides the Round Table JSON, this service
 * returns designed panels with null content.
 *
 * ── INTEGRATION POINT ──────────────────────────────────────────────────
 * When the backend provides Round Table data, replace the body of `get()` with
 * a real fetch + adapter mapping into `RoundTablePerspective[]`. Do NOT invent
 * the JSON contract.
 * ───────────────────────────────────────────────────────────────────────
 */

import { PendingContractError } from "../types/api";

export const roundTableService = {
  /** Fetch Round Table analysis. Throws PendingContractError until backend contract lands. */
  async get(): Promise<never> {
    throw new PendingContractError("round table");
  },
};
