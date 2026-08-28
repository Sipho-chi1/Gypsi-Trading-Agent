type Trade = {
  symbol: string;
  verdict_decision: "approve" | "downsize" | "reject";
  verdict_reason: string;
  status: string;
};

export default function TradeFeed({ trades }: { trades: Trade[] }) {
  if (!trades?.length) return <p>No trades yet — the worker hasn't run a cycle.</p>;
  return (
    <ul>
      {trades.map((t, i) => (
        <li key={i}>
          <strong>{t.symbol}</strong> — {t.verdict_decision} — {t.verdict_reason} ({t.status})
        </li>
      ))}
    </ul>
  );
}
