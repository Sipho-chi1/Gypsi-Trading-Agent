import { getTrades, getPerformance } from "../lib/api";
import TradeFeed from "../components/TradeFeed";
import PerformanceChart from "../components/PerformanceChart";

export default async function DashboardPage() {
  const [trades, performance] = await Promise.all([getTrades(), getPerformance()]);

  return (
    <main style={{ padding: 24 }}>
      <h1>Gypsi</h1>
      <p>Live trade feed and performance for the autonomous Round Table agent.</p>
      <PerformanceChart data={performance} />
      <TradeFeed trades={trades} />
    </main>
  );
}
