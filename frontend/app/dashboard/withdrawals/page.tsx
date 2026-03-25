"use client";

import { useQuery } from "@tanstack/react-query";
import { useCoop } from "@/context/CoopContext";
import { getWithdrawals } from "@/lib/api/cooperatives";
import { formatNaira, formatDateTime } from "@/lib/utils";
import { Skeleton } from "@/components/ui/Skeleton";
import { RecordWithdrawalButton } from "@/components/dashboard/RecordWithdrawalButton";

export default function WithdrawalsPage() {
  const { activeCoop } = useCoop();
  const coopId = activeCoop?.id ?? "";

  const { data, isLoading } = useQuery({
    queryKey: ["coop", coopId, "withdrawals"],
    queryFn: () => getWithdrawals(coopId),
    enabled: !!coopId,
  });

  const items = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">Withdrawals</h1>
        {activeCoop && <RecordWithdrawalButton coopId={coopId} />}
      </div>

      <div className="bg-white rounded-xl border border-border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                {[
                  "Date",
                  "Amount (₦)",
                  "Reason",
                  "Authorized By",
                  "Pool After",
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
                      {Array.from({ length: 5 }).map((_, j) => (
                        <td key={j} className="px-4 py-3">
                          <Skeleton className="h-4 w-24" />
                        </td>
                      ))}
                    </tr>
                  ))
                : items.map((w) => (
                    <tr
                      key={w.id}
                      className="hover:bg-muted/30 transition-colors"
                    >
                      <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">
                        {formatDateTime(w.created_at)}
                      </td>
                      <td className="px-4 py-3 font-medium text-foreground">
                        {formatNaira(w.amount)}
                      </td>
                      <td
                        className="px-4 py-3 text-foreground max-w-xs truncate"
                        title={w.reason}
                      >
                        {w.reason}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {w.authorized_by_name}
                      </td>
                      <td className="px-4 py-3 text-foreground">
                        {formatNaira(w.pool_balance_after)}
                      </td>
                    </tr>
                  ))}
              {!isLoading && items.length === 0 && (
                <tr>
                  <td
                    colSpan={5}
                    className="px-4 py-8 text-center text-muted-foreground text-sm"
                  >
                    No withdrawals recorded.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
