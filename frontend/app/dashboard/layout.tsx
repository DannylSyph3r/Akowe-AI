"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Sidebar } from "@/components/dashboard/Sidebar";
import { TopBar } from "@/components/dashboard/TopBar";
import { CoopProvider, useCoop } from "@/context/CoopContext";
import { getAccessToken } from "@/lib/api/auth";

function DashboardShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { allCoops, isLoading } = useCoop();

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
    }
  }, [router]);

  useEffect(() => {
    if (!isLoading && allCoops.length === 0 && pathname !== "/dashboard/setup") {
      router.replace("/dashboard/setup");
    }
  }, [isLoading, allCoops, router, pathname]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-muted">
        <div className="w-8 h-8 border-2 border-primary/20 border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-muted overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
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
