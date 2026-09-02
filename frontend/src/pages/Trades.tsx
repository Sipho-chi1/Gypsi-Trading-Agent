import { PageHeader } from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/EmptyState";
import { ListOrdered } from "lucide-react";

export default function Trades() {
  return (
    <div>
      <PageHeader
        title="Trades"
        description="Full GYPSI trade history with AI verdicts."
      />
      <EmptyState
        icon={<ListOrdered aria-hidden="true" className="h-6 w-6" />}
        title="Trade history coming soon"
        description="The trades table with verdict and status badges will land in the next build step."
      />
    </div>
  );
}
