"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  ScrollText,
  ArrowDownCircle,
  Settings,
  Radio,
  MessageSquare,
  Plus,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useCoop } from "@/context/CoopContext";
import type { CooperativeListItem } from "@/lib/api/types";

const NAV_ITEMS = [
  { label: "Overview", href: "/dashboard", icon: LayoutDashboard, exact: true },
  { label: "Members", href: "/dashboard/members", icon: Users, exact: false },
  {
    label: "History",
    href: "/dashboard/history",
    icon: ScrollText,
    exact: false,
  },
  {
    label: "Withdrawals",
    href: "/dashboard/withdrawals",
    icon: ArrowDownCircle,
    exact: false,
  },
  {
    label: "Broadcast",
    href: "/dashboard/broadcast",
    icon: Radio,
    exact: false,
  },
  {
    label: "AI Advisor",
    href: "/dashboard/chat",
    icon: MessageSquare,
    exact: false,
  },
  {
    label: "Settings",
    href: "/dashboard/settings",
    icon: Settings,
    exact: false,
  },
];

function CoopCard({
  coop,
  active,
  onClick,
}: {
  coop: CooperativeListItem;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full text-left px-3 py-2.5 rounded-lg transition-colors border",
        active
          ? "bg-primary/5 border-primary/20"
          : "border-transparent hover:bg-muted",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p
            className={cn(
              "text-sm font-medium truncate",
              active ? "text-primary" : "text-foreground",
            )}
          >
            {coop.name}
          </p>
          <p className="text-xs text-muted-foreground capitalize">
            {coop.role}
          </p>
        </div>
        {active && (
          <ChevronRight className="w-3.5 h-3.5 text-primary shrink-0" />
        )}
      </div>
    </button>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const { activeCoop, setActiveCoop, allCoops } = useCoop();

  const isActive = (href: string, exact: boolean) =>
    exact ? pathname === href : pathname.startsWith(href);

  return (
    <aside className="flex flex-col w-64 h-screen bg-white border-r border-border shrink-0">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center">
            <span className="text-white font-bold text-xs">A</span>
          </div>
          <span className="font-semibold text-foreground">AkoweAI</span>
        </div>
      </div>

      {/* Cooperative Switcher */}
      <div className="px-3 py-4 border-b border-border">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider px-3 mb-2">
          Cooperatives
        </p>
        <div className="space-y-1">
          {allCoops.map((coop) => (
            <CoopCard
              key={coop.id}
              coop={coop}
              active={activeCoop?.id === coop.id}
              onClick={() => setActiveCoop(coop)}
            />
          ))}
        </div>
        <Link
          href="/dashboard/setup"
          className="mt-2 flex items-center gap-2 w-full px-3 py-2 text-sm text-muted-foreground
                     hover:text-primary hover:bg-primary/5 rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Cooperative
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto scrollbar-thin">
        {NAV_ITEMS.map(({ label, href, icon: Icon, exact }) => {
          const active = isActive(href, exact);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                active
                  ? "bg-primary/5 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted",
              )}
            >
              <Icon className="w-4 h-4 shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
