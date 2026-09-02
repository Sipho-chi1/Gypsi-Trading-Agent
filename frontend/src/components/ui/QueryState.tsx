/**
 * QueryState — a declarative wrapper enforcing the four data states
 * (loading / error / empty / success) for every API-driven block.
 *
 * `error` may be a PendingContractError (awaiting backend) — pass `pendingState`
 * to render a designed placeholder instead of an error.
 */

import type { ReactNode } from "react";
import { isPendingContractError } from "../../types/api";
import { ErrorState } from "./ErrorState";
import { EmptyState } from "./EmptyState";

interface QueryStateProps<T> {
  isLoading: boolean;
  isError: boolean;
  error?: unknown;
  data: T | undefined;
  /** Whether the data is "empty" — triggers emptyState. */
  isEmpty?: (data: T) => boolean;
  loadingState?: ReactNode;
  emptyState?: ReactNode;
  errorState?: ReactNode;
  pendingState?: ReactNode;
  /** Fallback when none of the above render and data exists. */
  children: (data: T) => ReactNode;
}

export function QueryState<T>({
  isLoading,
  isError,
  error,
  data,
  isEmpty,
  loadingState,
  emptyState,
  errorState,
  pendingState,
  children,
}: QueryStateProps<T>) {
  if (isLoading && data === undefined) {
    return <>{loadingState ?? <DefaultLoading />}</>;
  }

  if (isError) {
    if (error && isPendingContractError(error) && pendingState) {
      return <>{pendingState}</>;
    }
    return <>{errorState ?? <ErrorState />}</>;
  }

  if (data === undefined) {
    return <>{errorState ?? <ErrorState />}</>;
  }

  if (isEmpty ? isEmpty(data) : isEmptyData(data)) {
    return <>{emptyState ?? <EmptyState title="Nothing here yet" />}</>;
  }

  return <>{children(data)}</>;
}

function DefaultLoading() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="h-20 animate-pulse rounded-card border bg-surface" />
      ))}
    </div>
  );
}

function isEmptyData(data: unknown): boolean {
  if (data == null) return true;
  if (Array.isArray(data)) return data.length === 0;
  if (typeof data === "object") return Object.keys(data).length === 0;
  return false;
}
