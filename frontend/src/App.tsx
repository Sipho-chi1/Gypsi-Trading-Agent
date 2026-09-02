import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import Overview from "./pages/Overview";
import Markets from "./pages/Markets";
import Trades from "./pages/Trades";
import TradeDetail from "./pages/TradeDetail";
import Positions from "./pages/Positions";
import Performance from "./pages/Performance";
import AiAnalysis from "./pages/AiAnalysis";
import Hermes from "./pages/Hermes";
import Risk from "./pages/Risk";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Overview />} />
          <Route path="markets" element={<Markets />} />
          <Route path="trades" element={<Trades />} />
          <Route path="trades/:id" element={<TradeDetail />} />
          <Route path="positions" element={<Positions />} />
          <Route path="performance" element={<Performance />} />
          <Route path="ai-analysis" element={<AiAnalysis />} />
          <Route path="hermes" element={<Hermes />} />
          <Route path="risk" element={<Risk />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<Overview />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
