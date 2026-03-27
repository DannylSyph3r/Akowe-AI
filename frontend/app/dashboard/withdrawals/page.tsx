"use client";

import { useQuery } from "@tanstack/react-query";
import { useCoop } from "@/context/CoopContext";
import { getWithdrawals } from "@/lib/api/cooperatives";
import { formatNaira, formatDateTime } from "@/lib/utils";
import { Skeleton } from "@/components/ui/Skeleton";
import { RecordWithdrawalButton } from "@/components/dashboard/RecordWithdrawalButton";

function WithdrawalCard({
  withdrawal,
}: {
  withdrawal: {
    id: string;
    amount: number;
    reason: string;
    authorized_by_name: string;
    pool_balance_after: number;
    created_at: string;
  };
}) {
  return (
    <article className="space-y-3 rounded-xl border border-border bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-foreground">
            {formatNaira(withdrawal.amount)}
          </h2>
          <p className="text-sm text-muted-foreground">
            {formatDateTime(withdrawal.created_at)}
          </p>
        </div>
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Withdrawal
        </p>
      </div>
      <dl className="space-y-3 text-sm">
        <div className="space-y-1">
          <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Reason
          </dt>
          <dd className="text-foreground">{withdrawal.reason}</dd>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Authorized By
            </dt>
            <dd className="text-foreground">{withdrawal.authorized_by_name}</dd>
          </div>
          <div className="space-y-1">
            <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Pool After
            </dt>
            <dd className="font-medium text-foreground">
              {formatNaira(withdrawal.pool_balance_after)}
            </dd>
          </div>
        </div>
      </dl>
    </article>
  );
}

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
    <div className="space-y-5 sm:space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <h1 className="text-xl font-semibold text-foreground">Withdrawals</h1>
        {activeCoop && (
          <RecordWithdrawalButton
            coopId={coopId}
            className="w-full sm:w-auto"
          />
        )}
      </div>

      <div className="bg-white rounded-xl border border-border overflow-hidden">
        <div className="space-y-3 p-4 md:hidden">
          {isLoading
            ? Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  className="space-y-3 rounded-xl border border-border bg-white p-4"
                >
                  <Skeleton className="h-5 w-28" />
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-16 w-full" />
                </div>
              ))
            : items.map((withdrawal) => (
                <WithdrawalCard key={withdrawal.id} withdrawal={withdrawal} />
              ))}
          {!isLoading && items.length === 0 && (
            <div className="rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
              No withdrawals recorded.
            </div>
          )}
        </div>

        <div className="hidden overflow-x-auto md:block">
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
