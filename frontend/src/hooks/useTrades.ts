import { useQuery } from "@tanstack/react-query";
import { tradesService } from "../services/tradesService";
import { POLL } from ".";

/** Latest trades — polled every ~15s. */
export function useTrades(limit?: number) {
  return useQuery({
    queryKey: ["trades", { limit }],
    queryFn: () => tradesService.list(limit),
    refetchInterval: POLL.trades,
    staleTime: POLL.trades,
    retry: 1,
  });
}

/** Resolve a single trade from the polled list (no invented GET /trades/{id}). */
export function useTradeById(id: number | string) {
  const trades = useTrades();
  return {
    ...trades,
    data: trades.data ? tradesService.findById(trades.data, id) : undefined,
  };
}
