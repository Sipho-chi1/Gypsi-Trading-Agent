import { cn } from "../../lib/cn";

interface ProgressBarProps {
  /** 0..1 */
  value: number;
  tone?: "accent" | "positive" | "negative" | "muted";
  className?: string;
  /** Accessible label for screen readers. */
  label?: string;
}

const toneClasses = {
  accent: "bg-accent",
  positive: "bg-positive",
  negative: "bg-negative",
  muted: "bg-muted",
};

export function ProgressBar({ value, tone = "accent", className, label }: ProgressBarProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const pct = `${Math.round(clamped * 100)}%`;
  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(clamped * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
      className={cn("h-1.5 w-full overflow-hidden rounded-pill bg-border/60", className)}
    >
      <div
        className={cn("h-full rounded-pill transition-[width] duration-300 ease-out", toneClasses[tone])}
        style={{ width: pct }}
      />
    </div>
  );
}
