/**
 * Confirmed contract: `GET /health`.
 */

import { apiRequest } from "./apiClient";
import type { HealthResponse } from "../types/api";

export const healthService = {
  /** Connectivity / liveness check. */
  check(): Promise<HealthResponse> {
    return apiRequest<HealthResponse>("/health");
  },
};
