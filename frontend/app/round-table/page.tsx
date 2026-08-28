import { getRoundTableFeed } from "../../lib/api";
import RoundTableCard from "../../components/RoundTableCard";

// This is the demo's best visual moment — invest UI polish time here.
export default async function RoundTablePage() {
  const feed = await getRoundTableFeed();

  return (
    <main style={{ padding: 24 }}>
      <h1>The Round Table</h1>
      <p>Every proposal, its independent read, and the verdict that followed.</p>
      {feed.map((entry: any, i: number) => (
        <RoundTableCard key={i} entry={entry} />
      ))}
    </main>
  );
}
