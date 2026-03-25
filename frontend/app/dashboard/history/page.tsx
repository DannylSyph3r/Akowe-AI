"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useCoop } from "@/context/CoopContext";
import {
  getPeriods,
  getContributionsSummary,
  getPeriodStatus,
} from "@/lib/api/cooperatives";
import { formatNaira, formatDate } from "@/lib/utils";
import { RiskBadge, Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";

export default function HistoryPage() {
  const { activeCoop } = useCoop();
  const coopId = activeCoop?.id ?? "";
  const [selectedPeriodId, setSelectedPeriodId] = useState<string>("all");

  const { data: periods = [], isLoading: periodsLoading } = useQuery({
    queryKey: ["coop", coopId, "periods"],
    queryFn: () => getPeriods(coopId),
    enabled: !!coopId,
  });

  const { data: summary = [], isLoading: summaryLoading } = useQuery({
    queryKey: ["coop", coopId, "contributions-summary"],
    queryFn: () => getContributionsSummary(coopId),
    enabled: !!coopId && selectedPeriodId === "all",
  });

  const { data: periodStatus = [], isLoading: statusLoading } = useQuery({
    queryKey: ["coop", coopId, "period-status", selectedPeriodId],
    queryFn: () => getPeriodStatus(coopId, selectedPeriodId),
    enabled: !!coopId && selectedPeriodId !== "all",
  });

  const isLoading = selectedPeriodId === "all" ? summaryLoading : statusLoading;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-semibold text-foreground">
          Contribution History
        </h1>
        <select
          className="rounded-lg border border-border bg-white px-3 py-2 text-sm text-foreground
                     focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary
                     transition-colors"
          value={selectedPeriodId}
          onChange={(e) => setSelectedPeriodId(e.target.value)}
          disabled={periodsLoading}
        >
          <option value="all">All time (leaderboard)</option>
          {periods.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label} {p.is_open ? "(current)" : ""}
            </option>
          ))}
        </select>
      </div>

      <div className="bg-white rounded-xl border border-border overflow-hidden">
        <div className="overflow-x-auto">
          {selectedPeriodId === "all" ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  {[
                    "#",
                    "Member",
                    "Total Contributed",
                    "Paid",
                    "Missed",
                    "Last Payment",
                    "Risk",
                  ].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {isLoading
                  ? Array.from({ length: 5 }).map((_, i) => (
                      <tr key={i}>
                        {Array.from({ length: 7 }).map((_, j) => (
                          <td key={j} className="px-4 py-3">
                            <Skeleton className="h-4 w-20" />
                          </td>
                        ))}
                      </tr>
                    ))
                  : summary.map((row, idx) => (
                      <tr
                        key={row.member_id}
                        className="hover:bg-muted/30 transition-colors"
                      >
                        <td className="px-4 py-3 text-muted-foreground font-mono text-xs">
                          {idx + 1}
                        </td>
                        <td className="px-4 py-3 font-medium text-foreground">
                          {row.full_name}
                        </td>
                        <td className="px-4 py-3 text-foreground">
                          {formatNaira(row.total_contributed)}
                        </td>
                        <td className="px-4 py-3 text-green-600 font-medium">
                          {row.periods_paid}
                        </td>
                        <td className="px-4 py-3 text-red-600 font-medium">
                          {row.periods_missed}
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {formatDate(row.last_payment_date)}
                        </td>
                        <td className="px-4 py-3">
                          <RiskBadge level={row.risk_level} />
                        </td>
                      </tr>
                    ))}
              </tbody>
            </table>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  {["Member", "Amount", "Status"].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {isLoading
                  ? Array.from({ length: 5 }).map((_, i) => (
                      <tr key={i}>
                        {Array.from({ length: 3 }).map((_, j) => (
                          <td key={j} className="px-4 py-3">
                            <Skeleton className="h-4 w-24" />
                          </td>
                        ))}
                      </tr>
                    ))
                  : periodStatus.map((row) => (
                      <tr
                        key={row.member_id}
                        className="hover:bg-muted/30 transition-colors"
                      >
                        <td className="px-4 py-3 font-medium text-foreground">
                          {row.full_name}
                        </td>
                        <td className="px-4 py-3 text-foreground">
                          {row.amount > 0 ? formatNaira(row.amount) : "—"}
                        </td>
                        <td className="px-4 py-3">
                          <Badge
                            variant={
                              row.status === "paid" ? "success" : "danger"
                            }
                          >
                            {row.status === "paid" ? "Paid" : "Unpaid"}
                          </Badge>
                        </td>
                      </tr>
                    ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
