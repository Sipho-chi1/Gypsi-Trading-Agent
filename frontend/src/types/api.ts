/**
 * Shared API types.
 *
 * GYPSI is a pure client of the FastAPI backend. No invented fields.
 */

/** A typed error raised by the API client for any non-2xx response. */
export class ApiError extends Error {
  readonly status: number;
  readonly statusText: string;
  readonly body: unknown;

  constructor(status: number, statusText: string, body: unknown) {
    super(`Request failed with status ${status} (${statusText})`);
    this.name = "ApiError";
    this.status = status;
    this.statusText = statusText;
    this.body = body;
  }
}

/**
 * Thrown by services whose backend contract is still being finalized
 * (positions, account, agent, round table, Hermes, markets).
 * The UI treats this as a designed "awaiting backend" state, never an error page.
 */
export class PendingContractError extends Error {
  readonly resource: string;

  constructor(resource: string) {
    super(`The backend contract for "${resource}" is not yet available.`);
    this.name = "PendingContractError";
    this.resource = resource;
  }
}

export function isPendingContractError(err: unknown): boolean {
  return err instanceof PendingContractError;
}

/** `GET /health` — connectivity check. Shape is minimal; tolerate extras. */
export interface HealthResponse {
  status?: string;
  [key: string]: unknown;
}
