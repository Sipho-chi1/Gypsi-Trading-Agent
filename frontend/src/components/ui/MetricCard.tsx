import type { ReactNode } from "react";
import { cn } from "../../lib/cn";
import { Skeleton } from "./Skeleton";

interface MetricCardProps {
  label: string;
  value: ReactNode;
  /** Optional delta/trend text (e.g. "+1.2% today"). */
  delta?: ReactNode;
  /** Tone for the value/delta (positive/negative/muted). */
  tone?: "default" | "positive" | "negative" | "accent";
  loading?: boolean;
  className?: string;
}

const toneClasses = {
  default: "text-foreground",
  positive: "text-positive",
  negative: "text-negative",
  accent: "text-accent",
};

/** Key-metric stat card. Numeric values use tabular numerals. */
export function MetricCard({
  label,
  value,
  delta,
  tone = "default",
  loading,
  className,
}: MetricCardProps) {
  return (
    <div
      className={cn(
        "rounded-card border bg-surface px-4 py-3.5 transition-colors duration-200",
        className,
      )}
    >
      <p className="text-[11px] font-medium uppercase tracking-wider text-muted">{label}</p>
      {loading ? (
        <Skeleton className="mt-2 h-6 w-24" />
      ) : (
        <p
          className={cn(
            "mt-1 text-xl font-semibold tabular tabular-nums leading-7 tracking-tight",
            toneClasses[tone],
          )}
        >
          {value}
        </p>
      )}
      {delta ? (
        <p className="mt-1 text-xs tabular tabular-nums text-muted">{delta}</p>
      ) : null}
    </div>
  );
}
