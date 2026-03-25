"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Copy, Check } from "lucide-react";
import { toast } from "sonner";
import { useCoop } from "@/context/CoopContext";
import { getMembers, generateJoinCodes } from "@/lib/api/cooperatives";
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

  const { data: members = [], isLoading } = useQuery({
    queryKey: ["coop", coopId, "members"],
    queryFn: () => getMembers(coopId),
    enabled: !!coopId,
  });

  const [search, setSearch] = useState("");
  const [count, setCount] = useState("5");
  const [expiry, setExpiry] = useState("30");
  const [generating, setGenerating] = useState(false);
  const [codes, setCodes] = useState<
    Array<{ code: string; expires_at: string }>
  >([]);

  const filtered = members.filter((m) =>
    m.full_name.toLowerCase().includes(search.toLowerCase()),
  );

  const handleGenerateCodes = async () => {
    setGenerating(true);
    try {
      const result = await generateJoinCodes(
        coopId,
        parseInt(count, 10),
        parseInt(expiry, 10),
      );
      setCodes(result.codes);
      toast.success(`${result.codes.length} join code(s) generated`);
    } catch {
      toast.error("Failed to generate join codes");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-foreground">Members</h1>

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
              {isLoading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i}>
                      {Array.from({ length: 6 }).map((_, j) => (
                        <td key={j} className="px-4 py-3">
                          <Skeleton className="h-4 w-24" />
                        </td>
                      ))}
                    </tr>
                  ))
                : filtered.map((m) => (
                    <tr
                      key={m.member_id}
                      className="hover:bg-muted/30 transition-colors"
                    >
                      <td className="px-4 py-3 font-medium text-foreground">
                        {m.full_name}
                      </td>
                      <td className="px-4 py-3 capitalize text-muted-foreground">
                        {m.role}
                      </td>
                      <td className="px-4 py-3 text-foreground">
                        {formatNaira(m.total_contributed)}
                      </td>
                      <td className="px-4 py-3 text-foreground">
                        {m.periods_paid}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {formatDate(m.last_paid_at)}
                      </td>
                      <td className="px-4 py-3">
                        <RiskBadge level={m.risk_level} />
                      </td>
                    </tr>
                  ))}
              {!isLoading && filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-muted-foreground text-sm"
                  >
                    No members found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-border p-5 space-y-4">
        <h2 className="text-base font-medium text-foreground">
          Generate Join Codes
        </h2>
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

        {codes.length > 0 && (
          <div className="space-y-1.5 max-h-60 overflow-y-auto scrollbar-thin">
            {codes.map(({ code, expires_at }) => (
              <div
                key={code}
                className="flex items-center justify-between bg-muted rounded-lg px-3 py-2"
              >
                <code className="text-sm font-mono text-foreground">
                  {code}
                </code>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">
                    Expires {formatDate(expires_at)}
                  </span>
                  <CopyButton text={code} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
