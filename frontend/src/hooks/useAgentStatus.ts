import { useQuery } from "@tanstack/react-query";
import { agentService } from "../services/agentService";
import { POLL } from ".";

/** Agent status — polled every ~5s. Never throws: OFFLINE is a valid state. */
export function useAgentStatus() {
  return useQuery({
    queryKey: ["agent-status"],
    queryFn: () => agentService.getStatus(),
    refetchInterval: POLL.agent,
    staleTime: POLL.agent,
    retry: false,
  });
}
