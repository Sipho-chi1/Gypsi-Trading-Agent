/**
 * Account — PENDING backend contract.
 *
 * Typed adapter pattern. Maps an eventual backend account response into the UI
 * `AccountSummary` model. Until the backend exposes account data, every call
 * reports PendingContractError — no fake balances.
 *
 * ── INTEGRATION POINT ──────────────────────────────────────────────────
 * When the backend provides account data (e.g. GET /account), replace the body
 * of `get()` with:
 *
 *   const raw = await apiRequest<unknown>("/account");
 *   return adaptAccount(raw); // map into AccountSummary — do NOT invent fields
 * ───────────────────────────────────────────────────────────────────────
 */

import { PendingContractError } from "../types/api";
import type { AccountSummary } from "../types/account";

export const accountService = {
  /** Fetch account summary. Throws PendingContractError until backend contract lands. */
  async get(): Promise<AccountSummary> {
    throw new PendingContractError("account");
  },
};
