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

function ContributionSummaryCard({
  index,
  row,
}: {
  index: number;
  row: {
    member_id: string;
    full_name: string;
    total_contributed: number;
    periods_paid: number;
    periods_missed: number;
    last_payment_date: string | null;
    risk_level: "LOW" | "MEDIUM" | "HIGH";
  };
}) {
  return (
    <article className="space-y-3 rounded-xl border border-border bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            #{index + 1}
          </p>
          <h2 className="truncate text-sm font-semibold text-foreground">
            {row.full_name}
          </h2>
        </div>
        <RiskBadge level={row.risk_level} />
      </div>
      <dl className="grid grid-cols-2 gap-3 text-sm">
        <div className="space-y-1">
          <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Total
          </dt>
          <dd className="font-medium text-foreground">
            {formatNaira(row.total_contributed)}
          </dd>
        </div>
        <div className="space-y-1">
          <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Paid
          </dt>
          <dd className="font-medium text-green-600">{row.periods_paid}</dd>
        </div>
        <div className="space-y-1">
          <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Missed
          </dt>
          <dd className="font-medium text-red-600">{row.periods_missed}</dd>
        </div>
        <div className="space-y-1">
          <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Last Payment
          </dt>
          <dd className="text-foreground">{formatDate(row.last_payment_date)}</dd>
        </div>
      </dl>
    </article>
  );
}

function PeriodStatusCard({
  row,
}: {
  row: {
    member_id: string;
    full_name: string;
    amount: number;
    status: "paid" | "unpaid";
  };
}) {
  return (
    <article className="space-y-3 rounded-xl border border-border bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <h2 className="min-w-0 truncate text-sm font-semibold text-foreground">
          {row.full_name}
        </h2>
        <Badge variant={row.status === "paid" ? "success" : "danger"}>
          {row.status === "paid" ? "Paid" : "Unpaid"}
        </Badge>
      </div>
      <div className="space-y-1 text-sm">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Amount
        </p>
        <p className="font-medium text-foreground">
          {row.amount > 0 ? formatNaira(row.amount) : "—"}
        </p>
      </div>
    </article>
  );
}

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
    <div className="space-y-5 sm:space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-xl font-semibold text-foreground">
          Contribution History
        </h1>
        <select
          className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm text-foreground
                     focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary
                     transition-colors sm:w-auto sm:min-w-72"
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
        <div className="space-y-3 p-4 md:hidden">
          {isLoading
            ? Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  className="space-y-3 rounded-xl border border-border bg-white p-4"
                >
                  <Skeleton className="h-5 w-32" />
                  <div className="grid grid-cols-2 gap-3">
                    <Skeleton className="h-10 w-full" />
                    <Skeleton className="h-10 w-full" />
                    <Skeleton className="h-10 w-full" />
                    <Skeleton className="h-10 w-full" />
                  </div>
                </div>
              ))
            : selectedPeriodId === "all"
              ? summary.map((row, idx) => (
                  <ContributionSummaryCard
                    key={row.member_id}
                    index={idx}
                    row={row}
                  />
                ))
              : periodStatus.map((row) => (
                  <PeriodStatusCard key={row.member_id} row={row} />
                ))}
          {!isLoading &&
            ((selectedPeriodId === "all" && summary.length === 0) ||
              (selectedPeriodId !== "all" && periodStatus.length === 0)) && (
              <div className="rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
                No contribution records found.
              </div>
            )}
        </div>

        <div className="hidden overflow-x-auto md:block">
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
