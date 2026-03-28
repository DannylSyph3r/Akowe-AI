"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { listCooperatives } from "@/lib/api/cooperatives";
import { getAccessToken } from "@/lib/api/auth";
import type { CooperativeListItem } from "@/lib/api/types";

interface CoopContextType {
  activeCoop: CooperativeListItem | null;
  setActiveCoop: (coop: CooperativeListItem) => void;
  allCoops: CooperativeListItem[];
  isLoading: boolean;
}

const CoopContext = createContext<CoopContextType | null>(null);

export function CoopProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [activeCoop, setActiveCoopState] = useState<CooperativeListItem | null>(
    null,
  );

  const { data: coops = [], isLoading } = useQuery({
    queryKey: ["cooperatives"],
    queryFn: listCooperatives,
    staleTime: 60_000,
    enabled: !!getAccessToken(),
  });

  // Restore saved selection or fall back to first coop
  useEffect(() => {
    if (coops.length === 0) return;

    const savedId =
      typeof window !== "undefined"
        ? localStorage.getItem("active_coop_id")
        : null;

    const candidate = savedId ? coops.find((c) => c.id === savedId) : null;
    const target = candidate ?? coops[0];

    setActiveCoopState((prev) => (prev?.id === target.id ? prev : target));
  }, [coops]);

  const setActiveCoop = useCallback(
    (coop: CooperativeListItem) => {
      setActiveCoopState(coop);
      localStorage.setItem("active_coop_id", coop.id);
      // Drop all coop-scoped queries so screens refetch for the new coop
      queryClient.removeQueries({ queryKey: ["coop"] });
    },
    [queryClient],
  );

  return (
    <CoopContext.Provider
      value={{ activeCoop, setActiveCoop, allCoops: coops, isLoading }}
    >
      {children}
    </CoopContext.Provider>
  );
}

export function useCoop() {
  const ctx = useContext(CoopContext);
  if (!ctx) throw new Error("useCoop must be used within CoopProvider");
  return ctx;
}
