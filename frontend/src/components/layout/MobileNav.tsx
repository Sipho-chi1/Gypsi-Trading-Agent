import { NavLink } from "react-router-dom";
import { cn } from "../../lib/cn";
import { NAV_ITEMS } from "./nav";

/**
 * Mobile bottom navigation — 5 priority destinations with icon + label.
 * Highlight active tab with accent; safe-area aware.
 */
export function MobileNav() {
  const items = NAV_ITEMS.filter((i) => i.mobile);
  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-40 flex border-t bg-surface pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === "/"}
          className={({ isActive }) =>
            cn(
              "flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px] font-medium transition-colors duration-150",
              "focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent",
              isActive ? "text-accent" : "text-muted hover:text-foreground",
            )
          }
        >
          {({ isActive }) => (
            <>
              <item.icon
                aria-hidden="true"
                className={cn("h-5 w-5", isActive && "text-accent")}
              />
              <span>{item.label}</span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}
