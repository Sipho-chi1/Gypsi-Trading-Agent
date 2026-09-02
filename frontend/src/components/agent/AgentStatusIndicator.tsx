import { cn } from "../../lib/cn";
import type { AgentState } from "../../types/agent";

interface AgentStatusIndicatorProps {
  state: AgentState;
  /** Show the textual state next to the dot. */
  showLabel?: boolean;
  className?: string;
}

/** Visual tone + pulse rules per agent display state. */
const STATE_STYLE: Record<AgentState, { dot: string; label: string; pulse: boolean }> = {
  ONLINE: { dot: "bg-positive", label: "text-positive", pulse: false },
  ANALYZING: { dot: "bg-accent", label: "text-accent", pulse: true },
  "TRADE IDENTIFIED": { dot: "bg-accent", label: "text-accent", pulse: true },
  EXECUTING: { dot: "bg-accent", label: "text-accent", pulse: true },
  MONITORING: { dot: "bg-muted", label: "text-muted", pulse: false },
  WAITING: { dot: "bg-muted", label: "text-muted", pulse: false },
  ERROR: { dot: "bg-negative", label: "text-negative", pulse: false },
  OFFLINE: { dot: "bg-negative/60", label: "text-muted", pulse: false },
  UNKNOWN: { dot: "bg-border", label: "text-muted", pulse: false },
};

/**
 * Live agent state indicator. Pulsing when the agent is actively working
 * (ANALYZING / TRADE IDENTIFIED / EXECUTING). Respects prefers-reduced-motion
 * via the global CSS override.
 */
export function AgentStatusIndicator({ state, showLabel = true, className }: AgentStatusIndicatorProps) {
  const style = STATE_STYLE[state] ?? STATE_STYLE.UNKNOWN;
  return (
    <span
      className={cn("inline-flex items-center gap-1.5", className)}
      title={`GYPSI agent: ${state}`}
    >
      <span
        aria-hidden="true"
        className={cn(
          "h-2 w-2 rounded-pill",
          style.dot,
          style.pulse && "animate-agent-pulse",
        )}
      />
      {showLabel ? (
        <span className={cn("text-xs font-semibold tracking-wide uppercase", style.label)}>
          {state}
        </span>
      ) : null}
    </span>
  );
}
