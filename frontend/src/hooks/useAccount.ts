import { useQuery } from "@tanstack/react-query";
import { accountService } from "../services/accountService";
import { POLL } from ".";

/** Account summary — polled every ~15s. PendingContractError until wired. */
export function useAccount() {
  return useQuery({
    queryKey: ["account"],
    queryFn: () => accountService.get(),
    refetchInterval: POLL.account,
    retry: false,
  });
}
