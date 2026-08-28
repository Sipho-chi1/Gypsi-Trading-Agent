const API_URL = process.env.NEXT_PUBLIC_API_URL;

export async function getTrades() {
  const res = await fetch(`${API_URL}/trades`, { cache: "no-store" });
  return res.json();
}

export async function getRoundTableFeed() {
  const res = await fetch(`${API_URL}/round-table/recent`, { cache: "no-store" });
  return res.json();
}

export async function getPerformance() {
  const res = await fetch(`${API_URL}/trades/performance`, { cache: "no-store" });
  return res.json();
}
