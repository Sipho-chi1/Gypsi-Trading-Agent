import { useQuery } from "@tanstack/react-query";
import { roundTableService } from "../services/roundTableService";
import { POLL } from ".";

/**
 * Round Table — polled. Until the backend contract lands the query errors with
 * PendingContractError; the page renders designed placeholder panels.
 */
export function useRoundTable() {
  return useQuery({
    queryKey: ["round-table"],
    queryFn: () => roundTableService.get(),
    refetchInterval: POLL.agent,
    retry: false,
  });
}
