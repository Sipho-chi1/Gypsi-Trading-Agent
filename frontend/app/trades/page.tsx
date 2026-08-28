import { getTrades } from "../../lib/api";
import TradeFeed from "../../components/TradeFeed";

export default async function TradesPage() {
  const trades = await getTrades();
  return (
    <main style={{ padding: 24 }}>
      <h1>Trade History</h1>
      <TradeFeed trades={trades} />
    </main>
  );
}
