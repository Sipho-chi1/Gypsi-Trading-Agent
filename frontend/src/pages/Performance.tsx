import { PageHeader } from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/EmptyState";
import { BarChart3 } from "lucide-react";

export default function Performance() {
  return (
    <div>
      <PageHeader
        title="Performance"
        description="Equity curve and trading performance."
      />
      <EmptyState
        icon={<BarChart3 aria-hidden="true" className="h-6 w-6" />}
        title="Performance charts coming soon"
        description="The equity curve and performance metrics will land with Recharts in the next build step."
      />
    </div>
  );
}
