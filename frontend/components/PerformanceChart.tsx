// TODO: replace with a real chart (e.g. recharts) once /trades/performance
// returns real aggregates.
export default function PerformanceChart({ data }: { data: any }) {
  return (
    <div>
      <p>Win rate: {data?.win_rate ?? "—"}</p>
      <p>Total trades: {data?.total_trades ?? 0}</p>
    </div>
  );
}
