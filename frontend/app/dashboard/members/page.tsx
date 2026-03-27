"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, Copy, Check } from "lucide-react";
import { toast } from "sonner";
import { useCoop } from "@/context/CoopContext";
import {
  getMembers,
  generateJoinCodes,
  getActiveJoinCodes,
  revokeJoinCode,
} from "@/lib/api/cooperatives";
import { formatNaira, formatDate } from "@/lib/utils";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { RiskBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={copy}
      className="text-muted-foreground hover:text-foreground transition-colors p-1"
    >
      {copied ? (
        <Check className="w-3.5 h-3.5 text-success" />
      ) : (
        <Copy className="w-3.5 h-3.5" />
      )}
    </button>
  );
}

export default function MembersPage() {
  const { activeCoop } = useCoop();
  const coopId = activeCoop?.id ?? "";
  const queryClient = useQueryClient();

  const { data: members = [], isLoading: membersLoading } = useQuery({
    queryKey: ["coop", coopId, "members"],
    queryFn: () => getMembers(coopId),
    enabled: !!coopId,
  });

  const { data: joinCodesData, isLoading: codesLoading } = useQuery({
    queryKey: ["coop", coopId, "join-codes"],
    queryFn: () => getActiveJoinCodes(coopId),
    enabled: !!coopId,
  });

  const activeCodes = joinCodesData?.codes ?? [];

  const [search, setSearch] = useState("");
  const [count, setCount] = useState("5");
  const [expiry, setExpiry] = useState("30");
  const [generating, setGenerating] = useState(false);
  const [revokingCode, setRevokingCode] = useState<string | null>(null);

  const filtered = members.filter((m) =>
    m.full_name.toLowerCase().includes(search.toLowerCase()),
  );

  const handleGenerateCodes = async () => {
    setGenerating(true);
    try {
      await generateJoinCodes(
        coopId,
        parseInt(count, 10),
        parseInt(expiry, 10),
      );
      await queryClient.invalidateQueries({
        queryKey: ["coop", coopId, "join-codes"],
      });
      toast.success(`${count} join code(s) generated`);
    } catch {
      toast.error("Failed to generate join codes");
    } finally {
      setGenerating(false);
    }
  };

  const handleRevoke = async (code: string) => {
    setRevokingCode(code);
    try {
      await revokeJoinCode(coopId, code);
      await queryClient.invalidateQueries({
        queryKey: ["coop", coopId, "join-codes"],
      });
      toast.success("Join code revoked");
    } catch {
      toast.error("Failed to revoke join code");
    } finally {
      setRevokingCode(null);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-foreground">Members</h1>

      {/* Member table */}
      <div className="bg-white rounded-xl border border-border overflow-hidden">
        <div className="p-4 border-b border-border">
          <Input
            icon={<Search className="w-4 h-4" />}
            placeholder="Search by name…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-xs"
          />
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                {[
                  "Name",
                  "Role",
                  "Total Contributed",
                  "Periods Paid",
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
              {membersLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 6 }).map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <Skeleton className="h-4 w-24" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : filtered.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-sm text-muted-foreground"
                  >
                    No members found.
                  </td>
                </tr>
              ) : (
                filtered.map((m) => (
                  <tr
                    key={String(m.member_id)}
                    className="hover:bg-muted/30 transition-colors"
                  >
                    <td className="px-4 py-3 font-medium text-foreground">
                      {m.full_name}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground capitalize">
                      {m.role}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatNaira(m.total_contributed)}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {m.periods_paid}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {m.last_paid_at ? formatDate(m.last_paid_at) : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <RiskBadge level={m.risk_level} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Join codes panel */}
      <div className="bg-white rounded-xl border border-border p-5 space-y-4">
        <h2 className="text-base font-medium text-foreground">Join Codes</h2>

        {/* Generation form */}
        <div className="flex items-end gap-3 flex-wrap">
          <Input
            label="Number of codes"
            type="number"
            min="1"
            max="50"
            value={count}
            onChange={(e) => setCount(e.target.value)}
            className="w-32"
          />
          <Input
            label="Expiry (days)"
            type="number"
            min="1"
            max="365"
            value={expiry}
            onChange={(e) => setExpiry(e.target.value)}
            className="w-32"
          />
          <Button onClick={handleGenerateCodes} loading={generating}>
            Generate
          </Button>
        </div>

        {/* Active codes table */}
        {codesLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : activeCodes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No active join codes. Generate some above.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  {["Code", "Type", "Expires", ""].map((h) => (
                    <th
                      key={h}
                      className="px-3 py-2 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {activeCodes.map((jc) => (
                  <tr
                    key={jc.code}
                    className="hover:bg-muted/30 transition-colors"
                  >
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1.5">
                        <code className="font-mono text-sm text-foreground">
                          {jc.code}
                        </code>
                        <CopyButton text={jc.code} />
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          jc.role === "exco"
                            ? "bg-purple-100 text-purple-700"
                            : "bg-blue-100 text-blue-700"
                        }`}
                      >
                        {jc.role === "exco" ? "👑 Exco" : "Member"}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-xs text-muted-foreground">
                      {formatDate(jc.expires_at)}
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <button
                        onClick={() => handleRevoke(jc.code)}
                        disabled={revokingCode === jc.code}
                        className="text-xs font-medium text-destructive hover:text-destructive/80 transition-colors disabled:opacity-50"
                      >
                        {revokingCode === jc.code ? "Revoking…" : "Revoke"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
