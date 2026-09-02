import { useQuery } from "@tanstack/react-query";
import { positionsService } from "../services/positionsService";
import { POLL } from ".";

/**
 * Open positions — polled every ~15s.
 * Until the backend contract lands the query errors with PendingContractError;
 * pages detect that (via isPendingContractError) and render an awaiting-backend
 * placeholder instead of an error page.
 */
export function usePositions() {
  return useQuery({
    queryKey: ["positions"],
    queryFn: () => positionsService.list(),
    refetchInterval: POLL.positions,
    retry: false,
  });
}
