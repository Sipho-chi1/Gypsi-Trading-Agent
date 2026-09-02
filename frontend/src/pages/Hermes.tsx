import { PageHeader } from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/EmptyState";
import { MessageSquare } from "lucide-react";

export default function Hermes() {
  return (
    <div>
      <PageHeader title="Hermes" description="Conversational interface" />
      <EmptyState
        icon={<MessageSquare aria-hidden="true" className="h-6 w-6" />}
        title="Hermes coming soon"
        description="The conversational interface will render here, wired to the Hermes adapter."
      />
    </div>
  );
}
