type Entry = {
  symbol: string;
  proposal_reasoning: string;
  independent_reasoning: string;
  decision: string;
  bias_flags: string[];
};

// TODO: style this as the actual "two seats at a table" deliberation view —
// proposal on one side, independent read on the other, verdict in the middle.
export default function RoundTableCard({ entry }: { entry: Entry }) {
  return (
    <div style={{ border: "1px solid #333", borderRadius: 8, padding: 16, marginBottom: 12 }}>
      <h3>{entry.symbol} — {entry.decision}</h3>
      <p><em>Proposal:</em> {entry.proposal_reasoning}</p>
      <p><em>Independent read:</em> {entry.independent_reasoning}</p>
      {entry.bias_flags?.length > 0 && (
        <p><em>Flags:</em> {entry.bias_flags.join(", ")}</p>
      )}
    </div>
  );
}
