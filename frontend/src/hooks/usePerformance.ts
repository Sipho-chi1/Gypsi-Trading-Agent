import { useQuery } from "@tanstack/react-query";
import { performanceService } from "../services/performanceService";
import { POLL } from ".";

/** Performance summary — polled every ~30s. */
export function usePerformance() {
  return useQuery({
    queryKey: ["performance"],
    queryFn: () => performanceService.get(),
    refetchInterval: POLL.performance,
    staleTime: POLL.performance,
    retry: 1,
  });
}
