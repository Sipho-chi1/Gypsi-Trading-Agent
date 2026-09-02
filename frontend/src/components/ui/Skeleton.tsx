import { cn } from "../../lib/cn";

/** Animated placeholder block used for loading states. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "animate-pulse rounded-md bg-border/60",
        className,
      )}
    />
  );
}
