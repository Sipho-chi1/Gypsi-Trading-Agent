/**
 * Hermes — PENDING backend contract.
 *
 * The conversational interface is UI-only until the backend Hermes endpoint
 * exists. Hermes never fabricates responses: until wired, sending a message
 * reports PendingContractError and the UI shows an "awaiting backend" state.
 *
 * ── INTEGRATION POINT ──────────────────────────────────────────────────
 * When the backend provides a Hermes endpoint (e.g. POST /hermes/chat),
 * implement `send()` with apiRequest + map the response into HermesMessage.
 * ───────────────────────────────────────────────────────────────────────
 */

import { PendingContractError } from "../types/api";
import type { HermesMessage } from "../types/hermes";

export const hermesService = {
  /** Check whether the backend Hermes endpoint is available. */
  async isAvailable(): Promise<boolean> {
    // INTEGRATION POINT: probe the real endpoint here when it exists.
    return false;
  },

  /** Send a message. Throws PendingContractError until the endpoint exists. */
  async send(_content: string): Promise<HermesMessage> {
    throw new PendingContractError("hermes");
  },
};
