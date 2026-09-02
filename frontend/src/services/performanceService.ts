/**
 * Confirmed contract: `GET /trades/performance`.
 *
 * IMPORTANT: the response shape is STILL being finalized. This service returns
 * a normalized `PerformanceSummary` with every field optional, tolerating shape
 * evolution. No invented metrics (no R-multiple).
 */

import { apiRequest } from "./apiClient";
import { normalizePerformance, type PerformanceSummary } from "../types/performance";

export const performanceService = {
  async get(): Promise<PerformanceSummary> {
    const raw = await apiRequest<unknown>("/trades/performance");
    return normalizePerformance(raw);
  },
};
