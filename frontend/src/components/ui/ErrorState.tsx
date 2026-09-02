import type { ReactNode } from "react";
import { cn } from "../../lib/cn";
import { Button } from "./Button";

interface ErrorStateProps {
  icon?: ReactNode;
  title?: string;
  description?: ReactNode;
  onRetry?: () => void;
  className?: string;
}

/** Human-readable error state with retry. Never exposes raw error codes. */
export function ErrorState({
  icon,
  title = "Something went wrong",
  description,
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-card border border-negative/25 bg-negative/5 px-6 py-8 text-center",
        className,
      )}
    >
      {icon ? <div className="mb-1 text-negative">{icon}</div> : null}
      <p className="text-sm font-semibold text-foreground">{title}</p>
      {description ? (
        <p className="max-w-sm text-xs leading-5 text-muted">{description}</p>
      ) : null}
      {onRetry ? (
        <div className="mt-2">
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Try again
          </Button>
        </div>
      ) : null}
    </div>
  );
}
