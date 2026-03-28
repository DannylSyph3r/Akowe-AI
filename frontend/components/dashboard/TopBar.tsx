"use client";

import { useRouter } from "next/navigation";
import { LogOut, User } from "lucide-react";
import { toast } from "sonner";
import { logout, getStoredUser } from "@/lib/api/auth";
import { useCoop } from "@/context/CoopContext";

export function TopBar() {
  const router = useRouter();
  const user = getStoredUser();
  const { activeCoop } = useCoop();

  const handleLogout = async () => {
    try {
      await logout();
      router.push("/login");
    } catch {
      toast.error("Failed to log out");
    }
  };

  return (
    <header className="h-14 bg-white border-b border-border px-6 flex items-center justify-between shrink-0">
      <div>
        {activeCoop && (
          <p className="text-sm font-medium text-foreground">
            {activeCoop.name}
          </p>
        )}
      </div>
      <div className="flex items-center gap-4">
        {user && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <User className="w-4 h-4" />
            <span>{user.full_name}</span>
          </div>
        )}
        <button
          onClick={handleLogout}
          className="flex items-center gap-1.5 text-sm text-muted-foreground
                     hover:text-foreground transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Logout
        </button>
      </div>
    </header>
  );
}
