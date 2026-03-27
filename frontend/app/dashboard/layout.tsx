"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { MobileNavDrawer, Sidebar } from "@/components/dashboard/Sidebar";
import { TopBar } from "@/components/dashboard/TopBar";
import { CoopProvider, useCoop } from "@/context/CoopContext";

function DashboardShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { allCoops, isLoading, isReady, hasAccessToken } = useCoop();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const requiresSetupRedirect =
    isReady &&
    hasAccessToken &&
    !isLoading &&
    allCoops.length === 0 &&
    pathname !== "/dashboard/setup";

  useEffect(() => {
    if (isReady && !hasAccessToken) {
      router.replace("/login");
    }
  }, [hasAccessToken, isReady, router]);

  useEffect(() => {
    if (requiresSetupRedirect) {
      router.replace("/dashboard/setup");
    }
  }, [requiresSetupRedirect, router]);

  if (!isReady || isLoading || !hasAccessToken || requiresSetupRedirect) {
    return (
      <div className="flex h-[100dvh] items-center justify-center bg-muted">
        <div className="w-8 h-8 border-2 border-primary/20 border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex h-[100dvh] min-h-0 overflow-hidden bg-muted">
      <Sidebar />
      <MobileNavDrawer
        open={mobileNavOpen}
        onClose={() => setMobileNavOpen(false)}
      />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <TopBar onOpenMobileNav={() => setMobileNavOpen(true)} />
        <main className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-5 lg:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <CoopProvider>
      <DashboardShell>{children}</DashboardShell>
    </CoopProvider>
  );
}
