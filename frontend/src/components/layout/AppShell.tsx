import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { MobileNav } from "./MobileNav";
import { MobileDrawer } from "./MobileDrawer";
import { ConnectivityBanner } from "./ConnectivityBanner";

/** Persistent command-center chrome around routed page content. */
export function AppShell() {
  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <ConnectivityBanner />
        <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-5 pb-24 sm:px-6 md:pb-6">
          <Outlet />
        </main>
      </div>
      <MobileDrawer />
      <MobileNav />
    </div>
  );
}
