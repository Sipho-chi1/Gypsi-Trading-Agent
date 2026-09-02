import { PageHeader } from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/EmptyState";
import { LayoutDashboard } from "lucide-react";

export default function Overview() {
  return (
    <div>
      <PageHeader
        title="Overview"
        description="What GYPSI is doing right now, and why."
      />
      <EmptyState
        icon={<LayoutDashboard aria-hidden="true" className="h-6 w-6" />}
        title="Dashboard coming together"
        description="Portfolio metrics, agent status, and the latest AI decision will land here in the next build steps."
      />
    </div>
  );
}
