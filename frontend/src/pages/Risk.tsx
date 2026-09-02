import { PageHeader } from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/EmptyState";
import { ShieldAlert } from "lucide-react";

export default function Risk() {
  return (
    <div>
      <PageHeader title="Risk" description="Risk summary" />
      <EmptyState
        icon={<ShieldAlert aria-hidden="true" className="h-6 w-6" />}
        title="Risk summary coming soon"
        description="A risk panel will render here via the adapter once a contract exists."
      />
    </div>
  );
}
