import { useUiStore } from "../../store/useUiStore";
import { Brand, NAV_ITEMS, SidebarLink } from "./nav";

/**
 * Persistent left sidebar. Hidden on mobile (drawer + bottom nav instead).
 * Collapsible to an icon rail on desktop via the UI store.
 */
export function Sidebar() {
  const collapsed = useUiStore((s) => s.sidebarCollapsed);

  return (
    <aside
      aria-label="Primary"
      className="sticky top-0 hidden h-screen shrink-0 flex-col border-r bg-surface md:flex"
    >
      <Brand collapsed={collapsed} />
      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-2 py-2">
        {NAV_ITEMS.map((item) => (
          <SidebarLink key={item.to} item={item} collapsed={collapsed} />
        ))}
      </nav>
      <div className="border-t px-3 py-3">
        <p className="text-[10px] uppercase tracking-wider text-muted">
          {collapsed ? "GYPSI" : "AI Trading Agent"}
        </p>
      </div>
    </aside>
  );
}
