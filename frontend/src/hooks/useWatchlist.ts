import { useQuery } from "@tanstack/react-query";
import { marketService } from "../services/marketService";
import { POLL } from ".";

/** Watchlist — marked frontend fallback until backend contract lands. */
export function useWatchlist() {
  return useQuery({
    queryKey: ["watchlist"],
    queryFn: () => marketService.getWatchlist(),
    refetchInterval: POLL.positions, // static fallback today; polling ready for real data
    retry: false,
  });
}
