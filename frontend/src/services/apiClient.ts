/**
 * Central API client.
 *
 * Single place that talks to the FastAPI backend. UI components NEVER call
 * fetch directly — they go through services that use this client.
 *
 * - Base URL: `VITE_API_URL` (Vite env, NOT Next.js) with a localhost fallback.
 * - Plain HTTP JSON request/response. NO WebSockets (polling only).
 * - Typed errors (ApiError) for any non-2xx response.
 * - Pluggable request hook so an auth token/header can be added later without
 *   rewriting the app. No auth today (internal tool).
 */

import { ApiError } from "../types/api";

const DEFAULT_BASE_URL = "http://localhost:8000";

export const API_BASE_URL: string =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/+$/, "") ??
  DEFAULT_BASE_URL;

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface ApiRequestOptions {
  method?: HttpMethod;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined>;
  /** Abort signal (e.g. for timeouts / unmounts). */
  signal?: AbortSignal;
  /** Override the default request timeout (ms). Default 15s. */
  timeoutMs?: number;
}

/** A hook that can mutate request init (e.g. attach auth headers later). */
export type RequestHook = (init: RequestInit) => RequestInit | Promise<RequestInit>;

let requestHook: RequestHook | null = null;

/**
 * Register a hook that runs before every request. Intended for future auth
 * token injection. Returns an unregister function.
 */
export function setRequestHook(hook: RequestHook | null): () => void {
  requestHook = hook;
  return () => {
    if (requestHook === hook) requestHook = null;
  };
}

function buildUrl(path: string, query?: ApiRequestOptions["query"]): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  if (!query) return `${API_BASE_URL}${normalized}`;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? `${API_BASE_URL}${normalized}?${qs}` : `${API_BASE_URL}${normalized}`;
}

/**
 * Core request helper. Throws `ApiError` on non-2xx and on network failure
 * (wrapped as an ApiError with status 0 so callers handle one error type).
 */
export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const {
    method = "GET",
    body,
    query,
    signal: externalSignal,
    timeoutMs = 15000,
  } = options;

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  const onExternalAbort = () => controller.abort();
  if (externalSignal) {
    if (externalSignal.aborted) controller.abort();
    else externalSignal.addEventListener("abort", onExternalAbort, { once: true });
  }

  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let init: RequestInit = {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal: controller.signal,
  };

  if (requestHook) {
    init = (await requestHook(init)) ?? init;
  }

  try {
    let response: Response;
    try {
      response = await fetch(buildUrl(path, query), init);
    } catch (err) {
      // Network failure or abort (timeout).
      if (controller.signal.aborted && !externalSignal?.aborted) {
        throw new ApiError(0, "timeout", { detail: "Request timed out." });
      }
      throw new ApiError(0, "network", {
        detail: err instanceof Error ? err.message : "Network request failed.",
      });
    }

    if (response.status === 204) return undefined as T;

    const text = await response.text();
    let data: unknown = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = text;
      }
    }

    if (!response.ok) {
      throw new ApiError(response.status, response.statusText, data);
    }
    return data as T;
  } finally {
    window.clearTimeout(timeout);
    if (externalSignal) externalSignal.removeEventListener("abort", onExternalAbort);
  }
}
