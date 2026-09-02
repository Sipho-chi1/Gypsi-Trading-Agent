import { useUiStore } from "../../store/useUiStore";
import { cn } from "../../lib/cn";
import { Brand, NAV_ITEMS, SidebarLink } from "./nav";

/**
 * Mobile slide-in drawer (left) for secondary navigation. Closes on
 * navigation, scrim click, or Escape. Focus trapped via inert on the rest.
 */
export function MobileDrawer() {
  const open = useUiStore((s) => s.mobileNavOpen);
  const setOpen = useUiStore((s) => s.setMobileNavOpen);

  return (
    <>
      {/* Scrim */}
      <div
        aria-hidden="true"
        onClick={() => setOpen(false)}
        className={cn(
          "fixed inset-0 z-40 bg-black/50 transition-opacity duration-250 md:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      />
      {/* Panel */}
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r bg-surface transition-transform duration-250 md:hidden",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <Brand />
        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-2 py-2">
          {NAV_ITEMS.map((item) => (
            <div key={item.to} onClick={() => setOpen(false)}>
              <SidebarLink item={item} />
            </div>
          ))}
        </nav>
      </aside>
    </>
  );
}
