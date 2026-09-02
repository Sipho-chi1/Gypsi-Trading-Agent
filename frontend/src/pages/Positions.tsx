import { PageHeader } from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/EmptyState";
import { Boxes } from "lucide-react";

export default function Positions() {
  return (
    <div>
      <PageHeader title="Positions" description="Open positions" />
      <EmptyState
        icon={<Boxes aria-hidden="true" className="h-6 w-6" />}
        title="Positions coming soon"
        description="Open positions will render here via the positions adapter."
      />
    </div>
  );
}
