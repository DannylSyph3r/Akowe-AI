"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Wallet,
  Users,
  TrendingUp,
  CalendarDays,
  Sparkles,
} from "lucide-react";
import { useCoop } from "@/context/CoopContext";
import { getCooperative, getInsights } from "@/lib/api/cooperatives";
import { formatNaira } from "@/lib/utils";
import { Skeleton } from "@/components/ui/Skeleton";
import { RecordWithdrawalButton } from "@/components/dashboard/RecordWithdrawalButton";

function MetricCard({
  title,
  value,
  icon: Icon,
  loading,
}: {
  title: string;
  value: string;
  icon: React.ElementType;
  loading: boolean;
}) {
  return (
    <div className="bg-white rounded-xl border border-border p-5 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">{title}</p>
        <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
          <Icon className="w-4 h-4 text-primary" />
        </div>
      </div>
      {loading ? (
        <Skeleton className="h-8 w-32" />
      ) : (
        <p className="text-2xl font-semibold text-foreground">{value}</p>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const { activeCoop } = useCoop();
  const coopId = activeCoop?.id ?? "";

  const { data: coop, isLoading: coopLoading } = useQuery({
    queryKey: ["coop", coopId, "detail"],
    queryFn: () => getCooperative(coopId),
    enabled: !!coopId,
  });

  const { data: insight, isLoading: insightLoading } = useQuery({
    queryKey: ["coop", coopId, "insights"],
    queryFn: () => getInsights(coopId),
    enabled: !!coopId,
    staleTime: 5 * 60_000,
  });

  const loading = coopLoading || !coop;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Overview</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {activeCoop?.name ?? "Loading..."}
          </p>
        </div>
        {activeCoop && <RecordWithdrawalButton coopId={coopId} />}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Pool Balance"
          value={coop ? formatNaira(coop.pool_balance) : "—"}
          icon={Wallet}
          loading={loading}
        />
        <MetricCard
          title="Total Members"
          value={coop ? String(coop.member_count) : "—"}
          icon={Users}
          loading={loading}
        />
        <MetricCard
          title="Collection Rate"
          value={coop ? `${coop.collection_rate_pct}%` : "—"}
          icon={TrendingUp}
          loading={loading}
        />
        <MetricCard
          title="YTD Collected"
          value={coop ? formatNaira(coop.ytd_collected_kobo) : "—"}
          icon={CalendarDays}
          loading={loading}
        />
      </div>

      <div className="bg-white rounded-xl border border-border p-5">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-lg bg-secondary/10 flex items-center justify-center shrink-0 mt-0.5">
            <Sparkles className="w-4 h-4 text-secondary" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground mb-1">
              AI Insight
            </p>
            {insightLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                {insight?.insight ?? "No insight available."}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
