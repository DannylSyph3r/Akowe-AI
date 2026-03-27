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
      type="button"
      onClick={copy}
      className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-white hover:text-foreground"
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-success" />
      ) : (
        <Copy className="h-3.5 w-3.5" />
      )}
    </button>
  );
}

function JoinCodeRoleBadge({ role }: { role: string }) {
  const isExco = role === "exco";

  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
        isExco ? "bg-purple-100 text-purple-700" : "bg-blue-100 text-blue-700"
      }`}
    >
      {isExco ? "Exco" : "Member"}
    </span>
  );
}

function MemberCard({
  member,
}: {
  member: {
    member_id: string;
    full_name: string;
    role: string;
    total_contributed: number;
    periods_paid: number;
    last_paid_at: string | null;
    risk_level: "LOW" | "MEDIUM" | "HIGH";
  };
}) {
  return (
    <article className="space-y-3 rounded-xl border border-border bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-sm font-semibold text-foreground">
            {member.full_name}
          </h2>
          <p className="text-sm capitalize text-muted-foreground">
            {member.role}
          </p>
        </div>
        <RiskBadge level={member.risk_level} />
      </div>
      <dl className="grid grid-cols-2 gap-3 text-sm">
        <div className="space-y-1">
          <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Total Contributed
          </dt>
          <dd className="font-medium text-foreground">
            {formatNaira(member.total_contributed)}
          </dd>
        </div>
        <div className="space-y-1">
          <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Periods Paid
          </dt>
          <dd className="font-medium text-foreground">{member.periods_paid}</dd>
        </div>
        <div className="col-span-2 space-y-1">
          <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Last Payment
          </dt>
          <dd className="text-foreground">{formatDate(member.last_paid_at)}</dd>
        </div>
      </dl>
    </article>
  );
}

function JoinCodeCard({
  code,
  expiresAt,
  role,
  revoking,
  onRevoke,
}: {
  code: string;
  expiresAt: string;
  role: string;
  revoking: boolean;
  onRevoke: () => void;
}) {
  return (
    <article className="space-y-3 rounded-xl border border-border bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Join Code
          </p>
          <code className="block break-all text-sm font-mono text-foreground">
            {code}
          </code>
        </div>
        <CopyButton text={code} />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Role
          </p>
          <JoinCodeRoleBadge role={role} />
        </div>
        <div className="space-y-1 text-right">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Expires
          </p>
          <p className="text-sm text-foreground">{formatDate(expiresAt)}</p>
        </div>
      </div>

      <div className="flex justify-end">
        <button
          type="button"
          onClick={onRevoke}
          disabled={revoking}
          className="text-xs font-medium text-destructive transition-colors hover:text-destructive/80 disabled:opacity-50"
        >
          {revoking ? "Revoking..." : "Revoke"}
        </button>
      </div>
    </article>
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

  const filtered = members.filter((member) =>
    member.full_name.toLowerCase().includes(search.toLowerCase()),
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
    <div className="space-y-5 sm:space-y-6">
      <h1 className="text-xl font-semibold text-foreground">Members</h1>

      <div className="overflow-hidden rounded-xl border border-border bg-white">
        <div className="border-b border-border p-4">
          <Input
            icon={<Search className="h-4 w-4" />}
            placeholder="Search by name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full sm:max-w-xs"
          />
        </div>

        <div className="space-y-3 p-4 md:hidden">
          {membersLoading
            ? Array.from({ length: 4 }).map((_, index) => (
                <div
                  key={index}
                  className="space-y-3 rounded-xl border border-border bg-white p-4"
                >
                  <Skeleton className="h-5 w-40" />
                  <div className="grid grid-cols-2 gap-3">
                    <Skeleton className="h-10 w-full" />
                    <Skeleton className="h-10 w-full" />
                    <Skeleton className="col-span-2 h-10 w-full" />
                  </div>
                </div>
              ))
            : filtered.map((member) => (
                <MemberCard key={member.member_id} member={member} />
              ))}
          {!membersLoading && filtered.length === 0 && (
            <div className="rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
              No members found.
            </div>
          )}
        </div>

        <div className="hidden overflow-x-auto md:block">
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
                ].map((heading) => (
                  <th
                    key={heading}
                    className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground"
                  >
                    {heading}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {membersLoading
                ? Array.from({ length: 5 }).map((_, rowIndex) => (
                    <tr key={rowIndex}>
                      {Array.from({ length: 6 }).map((_, cellIndex) => (
                        <td key={cellIndex} className="px-4 py-3">
                          <Skeleton className="h-4 w-24" />
                        </td>
                      ))}
                    </tr>
                  ))
                : filtered.map((member) => (
                    <tr
                      key={String(member.member_id)}
                      className="transition-colors hover:bg-muted/30"
                    >
                      <td className="px-4 py-3 font-medium text-foreground">
                        {member.full_name}
                      </td>
                      <td className="px-4 py-3 capitalize text-muted-foreground">
                        {member.role}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {formatNaira(member.total_contributed)}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {member.periods_paid}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {member.last_paid_at ? formatDate(member.last_paid_at) : "-"}
                      </td>
                      <td className="px-4 py-3">
                        <RiskBadge level={member.risk_level} />
                      </td>
                    </tr>
                  ))}
              {!membersLoading && filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-sm text-muted-foreground"
                  >
                    No members found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="space-y-4 rounded-xl border border-border bg-white p-4 sm:p-5">
        <h2 className="text-base font-medium text-foreground">Join Codes</h2>

        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
          <Input
            label="Number of codes"
            type="number"
            min="1"
            max="50"
            value={count}
            onChange={(e) => setCount(e.target.value)}
            className="w-full sm:w-32"
          />
          <Input
            label="Expiry (days)"
            type="number"
            min="1"
            max="365"
            value={expiry}
            onChange={(e) => setExpiry(e.target.value)}
            className="w-full sm:w-32"
          />
          <Button
            onClick={handleGenerateCodes}
            loading={generating}
            className="w-full sm:w-auto"
          >
            Generate
          </Button>
        </div>

        {codesLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, index) => (
              <Skeleton key={index} className="h-10 w-full" />
            ))}
          </div>
        ) : activeCodes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No active join codes. Generate some above.
          </p>
        ) : (
          <>
            <div className="space-y-3 md:hidden">
              {activeCodes.map((joinCode) => (
                <JoinCodeCard
                  key={joinCode.code}
                  code={joinCode.code}
                  expiresAt={joinCode.expires_at}
                  role={joinCode.role}
                  revoking={revokingCode === joinCode.code}
                  onRevoke={() => handleRevoke(joinCode.code)}
                />
              ))}
            </div>

            <div className="hidden overflow-x-auto md:block">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    {["Code", "Type", "Expires", ""].map((heading) => (
                      <th
                        key={heading}
                        className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground"
                      >
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {activeCodes.map((joinCode) => (
                    <tr
                      key={joinCode.code}
                      className="transition-colors hover:bg-muted/30"
                    >
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-1.5">
                          <code className="font-mono text-sm text-foreground">
                            {joinCode.code}
                          </code>
                          <CopyButton text={joinCode.code} />
                        </div>
                      </td>
                      <td className="px-3 py-2.5">
                        <JoinCodeRoleBadge role={joinCode.role} />
                      </td>
                      <td className="px-3 py-2.5 text-xs text-muted-foreground">
                        {formatDate(joinCode.expires_at)}
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <button
                          type="button"
                          onClick={() => handleRevoke(joinCode.code)}
                          disabled={revokingCode === joinCode.code}
                          className="text-xs font-medium text-destructive transition-colors hover:text-destructive/80 disabled:opacity-50"
                        >
                          {revokingCode === joinCode.code ? "Revoking..." : "Revoke"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
