import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Use raised surface instead of surface. */
  raised?: boolean;
  /** Interactive card (hover state + cursor pointer). */
  interactive?: boolean;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, raised, interactive, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "rounded-card border bg-surface transition-colors duration-200",
        raised && "bg-raised",
        interactive &&
          "cursor-pointer hover:border-accent/60 hover:bg-raised focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent",
        className,
      )}
      {...props}
    />
  ),
);
Card.displayName = "Card";

/** Card header row: title + optional trailing slot. */
export function CardHeader({
  title,
  subtitle,
  trailing,
  className,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  trailing?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-3", className)}>
      <div className="min-w-0">
        <h3 className="text-sm font-semibold tracking-tight text-foreground">{title}</h3>
        {subtitle ? (
          <p className="mt-0.5 text-xs text-muted">{subtitle}</p>
        ) : null}
      </div>
      {trailing ? <div className="shrink-0">{trailing}</div> : null}
    </div>
  );
}
