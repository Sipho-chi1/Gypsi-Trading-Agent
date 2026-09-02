import { PageHeader } from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/EmptyState";
import { FileSearch } from "lucide-react";

export default function TradeDetail() {
  return (
    <div>
      <PageHeader title="Trade Detail" />
      <EmptyState
        icon={<FileSearch aria-hidden="true" className="h-6 w-6" />}
        title="Select a trade"
        description="Open a trade from the Trades page to see the full GYPSI decision."
      />
    </div>
  );
}
