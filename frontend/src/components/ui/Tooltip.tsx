import { useId, type ReactNode } from "react";
import { cn } from "../../lib/cn";

interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  className?: string;
}

/**
 * Lightweight accessible tooltip. The trigger element carries
 * aria-describedby pointing at the tooltip; the tooltip is hidden from the
 * a11y tree until shown via hover/focus.
 */
export function Tooltip({ content, children, className }: TooltipProps) {
  const id = useId();
  return (
    <span className={cn("group/tooltip relative inline-flex", className)}>
      {children}
      <span
        role="tooltip"
        id={id}
        className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-1.5 -translate-x-1/2 whitespace-nowrap rounded-md border border-border bg-raised px-2 py-1 text-xs font-medium text-foreground opacity-0 shadow-lg transition-opacity duration-150 group-hover/tooltip:opacity-100 group-focus-within/tooltip:opacity-100"
      >
        {content}
      </span>
    </span>
  );
}
