import { PageHeader } from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/EmptyState";
import { Bot } from "lucide-react";

export default function AiAnalysis() {
  return (
    <div>
      <PageHeader
        title="AI Analysis"
        description="Round Table — the analytical perspectives behind GYPSI's verdict."
      />
      <EmptyState
        icon={<Bot aria-hidden="true" className="h-6 w-6" />}
        title="Round Table coming soon"
        description="Perspectives, consensus and the final GYPSI verdict will render here via the adapter."
      />
    </div>
  );
}
