import type { HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

type BadgeVariant =
  | "default"
  | "accent"
  | "positive"
  | "negative"
  | "warning"
  | "muted"
  | "outline";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const variantClasses: Record<BadgeVariant, string> = {
  default: "bg-surface text-foreground border-border",
  accent:
    "bg-accent text-on-accent border-accent font-semibold",
  positive:
    "bg-positive/10 text-positive border-positive/30",
  negative: "bg-negative/10 text-negative border-negative/30",
  warning:
    "bg-accent/15 text-accent border-accent/30",
  muted: "bg-muted/10 text-muted border-border",
  outline: "bg-transparent text-foreground border-border",
};

export function Badge({ variant = "default", className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-pill border px-2 py-0.5 text-[11px] font-medium leading-4 tracking-wide",
        variantClasses[variant],
        className,
      )}
      {...props}
    />
  );
}
