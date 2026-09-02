import { useQuery } from "@tanstack/react-query";
import { healthService } from "../services/healthService";
import { POLL } from ".";

/** Backend connectivity — polled every ~30s. */
export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => healthService.check(),
    refetchInterval: POLL.health,
    retry: 1,
    staleTime: POLL.health,
    // No throwOnError — callers read `.isError` to show a connectivity banner.
  });
}
