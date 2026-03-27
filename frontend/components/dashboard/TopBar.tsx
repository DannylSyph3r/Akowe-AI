"use client";

import { useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import { LogOut, Menu, User } from "lucide-react";
import { logout } from "@/lib/api/auth";
import { useCoop } from "@/context/CoopContext";
import type { StoredUser } from "@/lib/api/types";

const noopSubscribe = () => () => {};

export function TopBar({
  onOpenMobileNav,
}: {
  onOpenMobileNav: () => void;
}) {
  const router = useRouter();
  const storedUser = useSyncExternalStore(
    noopSubscribe,
    () => (typeof window === "undefined" ? null : localStorage.getItem("user")),
    () => null,
  );
  const { activeCoop } = useCoop();
  let user: StoredUser | null = null;

  if (storedUser) {
    try {
      user = JSON.parse(storedUser) as StoredUser;
    } catch {
      user = null;
    }
  }

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <header className="sticky top-0 z-20 flex min-h-14 shrink-0 items-center justify-between border-b border-border bg-white/95 px-3 backdrop-blur sm:px-4 lg:px-6">
      <div className="flex min-w-0 items-center gap-2 sm:gap-3">
        <button
          type="button"
          onClick={onOpenMobileNav}
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground lg:hidden"
          aria-label="Open navigation"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-foreground">
            {activeCoop?.name ?? "Dashboard"}
          </p>
          <p className="hidden text-xs text-muted-foreground sm:block">
            Cooperative dashboard
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 sm:gap-3">
        {user && (
          <div className="hidden items-center gap-2 text-sm text-muted-foreground sm:flex">
            <User className="w-4 h-4" />
            <span className="max-w-40 truncate">{user.full_name}</span>
          </div>
        )}
        <button
          type="button"
          onClick={handleLogout}
          className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground sm:px-3"
        >
          <LogOut className="w-4 h-4" />
          <span className="hidden sm:inline">Logout</span>
        </button>
      </div>
    </header>
  );
}
