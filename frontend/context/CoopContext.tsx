"use client";

import {
  createContext,
  useCallback,
  useContext,
  useState,
  useSyncExternalStore,
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
  isReady: boolean;
  hasAccessToken: boolean;
}

const CoopContext = createContext<CoopContextType | null>(null);
const noopSubscribe = () => () => {};

export function CoopProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [selectedCoopId, setSelectedCoopId] = useState<string | null>(
    typeof window === "undefined"
      ? null
      : localStorage.getItem("active_coop_id"),
  );
  const isReady = useSyncExternalStore(noopSubscribe, () => true, () => false);
  const accessToken = useSyncExternalStore(
    noopSubscribe,
    getAccessToken,
    () => null,
  );
  const hasAccessToken = !!accessToken;

  const { data: coops = [], isLoading: isCoopsLoading } = useQuery({
    queryKey: ["cooperatives"],
    queryFn: listCooperatives,
    staleTime: 60_000,
    enabled: isReady && hasAccessToken,
  });

  const isLoading = !isReady || (hasAccessToken && isCoopsLoading);
  const activeCoop =
    (selectedCoopId ? coops.find((coop) => coop.id === selectedCoopId) : null) ??
    coops[0] ??
    null;

  const setActiveCoop = useCallback(
    (coop: CooperativeListItem) => {
      setSelectedCoopId(coop.id);
      localStorage.setItem("active_coop_id", coop.id);
      // Drop all coop-scoped queries so screens refetch for the new coop
      queryClient.removeQueries({ queryKey: ["coop"] });
    },
    [queryClient],
  );

  return (
    <CoopContext.Provider
      value={{
        activeCoop,
        setActiveCoop,
        allCoops: coops,
        isLoading,
        isReady,
        hasAccessToken,
      }}
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
