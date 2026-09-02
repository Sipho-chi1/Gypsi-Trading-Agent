import { NavLink } from "react-router-dom";
import {
  Activity,
  BarChart3,
  Bot,
  LayoutDashboard,
  ListOrdered,
  MessageSquare,
  ScrollText,
  Settings,
  ShieldAlert,
  type LucideIcon,
} from "lucide-react";
import { cn } from "../../lib/cn";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Shown in the mobile bottom bar (max 5, icon+label). */
  mobile?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Overview", icon: LayoutDashboard, mobile: true },
  { to: "/markets", label: "Markets", icon: Activity },
  { to: "/trades", label: "Trades", icon: ListOrdered, mobile: true },
  { to: "/positions", label: "Positions", icon: ScrollText, mobile: true },
  { to: "/performance", label: "Performance", icon: BarChart3, mobile: true },
  { to: "/ai-analysis", label: "AI Analysis", icon: Bot },
  { to: "/hermes", label: "Hermes", icon: MessageSquare, mobile: true },
  { to: "/risk", label: "Risk", icon: ShieldAlert },
  { to: "/settings", label: "Settings", icon: Settings },
];

/** Sidebar brand header (logo + wordmark). */
export function Brand({ collapsed }: { collapsed?: boolean }) {
  return (
    <div className="flex items-center gap-2.5 px-3 py-4">
      <img
        src="/gypsi-mark.svg"
        alt="GYPSI logo"
        className="h-8 w-8 shrink-0"
        width={32}
        height={32}
      />
      {!collapsed ? (
        <span className="text-base font-bold tracking-[0.18em] text-foreground">
          GYPSI
        </span>
      ) : null}
    </div>
  );
}

export function SidebarLink({ item, collapsed }: { item: NavItem; collapsed?: boolean }) {
  return (
    <NavLink
      to={item.to}
      end={item.to === "/"}
      className={({ isActive }) =>
        cn(
          "group flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-150",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
          collapsed ? "justify-center px-2" : "",
          isActive
            ? "bg-accent/12 text-accent"
            : "text-muted hover:bg-surface hover:text-foreground",
        )
      }
      title={collapsed ? item.label : undefined}
    >
      {({ isActive }) => (
        <>
          <item.icon
            aria-hidden="true"
            className={cn(
              "h-[18px] w-[18px] shrink-0 transition-colors duration-150",
              isActive ? "text-accent" : "text-muted group-hover:text-foreground",
            )}
          />
          {!collapsed ? <span>{item.label}</span> : null}
        </>
      )}
    </NavLink>
  );
}
