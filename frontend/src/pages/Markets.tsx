import { PageHeader } from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/EmptyState";
import { Activity } from "lucide-react";

export default function Markets() {
  return (
    <div>
      <PageHeader title="Markets" description="Watchlist" />
      <EmptyState
        icon={<Activity aria-hidden="true" className="h-6 w-6" />}
        title="Watchlist coming soon"
        description="SPY, QQQ, AAPL, MSFT and NVDA will appear here as the marked frontend fallback."
      />
    </div>
  );
}
