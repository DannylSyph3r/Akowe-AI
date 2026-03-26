"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Copy, Check } from "lucide-react";
import { toast } from "sonner";
import { createCooperative, generateExcoInvite } from "@/lib/api/cooperatives";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

const FREQUENCY_OPTIONS = [
  { value: "weekly", label: "Weekly" },
  { value: "biweekly", label: "Bi-weekly" },
  { value: "triweekly", label: "Tri-weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "bimonthly", label: "Bi-monthly" },
  { value: "quarterly", label: "Quarterly" },
  { value: "yearly", label: "Yearly" },
];

function CopyField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <div className="flex items-center gap-2 bg-muted rounded-lg px-3 py-2">
        <code className="flex-1 text-sm font-mono text-foreground truncate">
          {value}
        </code>
        <button
          onClick={copy}
          className="text-muted-foreground hover:text-foreground transition-colors"
        >
          {copied ? (
            <Check className="w-4 h-4 text-success" />
          ) : (
            <Copy className="w-4 h-4" />
          )}
        </button>
      </div>
    </div>
  );
}

export default function SetupPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [form, setForm] = useState({
    name: "",
    contributionAmountNaira: "",
    frequency: "monthly",
    anchorDate: "",
    dueDayOffset: "3",
  });
  const [loading, setLoading] = useState(false);
  const [created, setCreated] = useState<{
    coopId: string;
    joinCode: string;
  } | null>(null);
  const [excoCode, setExcoCode] = useState<string | null>(null);
  const [generatingExco, setGeneratingExco] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const amountKobo = Math.round(
      parseFloat(form.contributionAmountNaira) * 100,
    );
    if (!amountKobo || amountKobo <= 0) {
      toast.error("Enter a valid contribution amount");
      return;
    }
    setLoading(true);
    try {
      const result = await createCooperative({
        name: form.name.trim(),
        contribution_amount_kobo: amountKobo,
        frequency: form.frequency,
        anchor_date: form.anchorDate,
        due_day_offset: parseInt(form.dueDayOffset, 10),
      });
      setCreated({ coopId: result.cooperative_id, joinCode: result.join_code });
      queryClient.invalidateQueries({ queryKey: ["cooperatives"] });
    } catch (err: any) {
      toast.error(
        err?.response?.data?.message ?? "Failed to create cooperative",
      );
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateExcoInvite = async () => {
    if (!created) return;
    setGeneratingExco(true);
    try {
      const result = await generateExcoInvite(created.coopId, 30);
      setExcoCode(result.code);
    } catch {
      toast.error("Failed to generate exco invite code");
    } finally {
      setGeneratingExco(false);
    }
  };

  if (created) {
    return (
      <div className="max-w-lg mx-auto">
        <div className="bg-white rounded-xl border border-border shadow-sm p-6 space-y-6">
          <div>
            <h1 className="text-lg font-semibold text-foreground">
              Cooperative Created!
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Share these codes with your members.
            </p>
          </div>

          <CopyField label="Member Join Code" value={created.joinCode} />

          {excoCode ? (
            <CopyField label="Exco Invite Code" value={excoCode} />
          ) : (
            <Button
              variant="outline"
              onClick={handleGenerateExcoInvite}
              loading={generatingExco}
              className="w-full"
            >
              Generate Exco Invite Code
            </Button>
          )}

          <Button className="w-full" onClick={() => router.push("/dashboard")}>
            Go to Dashboard
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">
          Create Cooperative
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Set up your cooperative's contribution schedule.
        </p>
      </div>

      <div className="bg-white rounded-xl border border-border shadow-sm p-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Cooperative Name"
            placeholder="e.g. Eko Women Ajo"
            value={form.name}
            onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
            required
          />
          <Input
            label="Contribution Amount (₦)"
            type="number"
            min="1"
            step="1"
            placeholder="e.g. 10000"
            value={form.contributionAmountNaira}
            onChange={(e) =>
              setForm((p) => ({
                ...p,
                contributionAmountNaira: e.target.value,
              }))
            }
            required
          />
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-foreground">
              Frequency
            </label>
            <select
              className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm
                         text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20
                         focus:border-primary transition-colors"
              value={form.frequency}
              onChange={(e) =>
                setForm((p) => ({ ...p, frequency: e.target.value }))
              }
            >
              {FREQUENCY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <Input
            label="Anchor Date"
            type="date"
            value={form.anchorDate}
            onChange={(e) =>
              setForm((p) => ({ ...p, anchorDate: e.target.value }))
            }
            required
          />
          <Input
            label="Due Day Offset (days after period start)"
            type="number"
            min="0"
            max="60"
            value={form.dueDayOffset}
            onChange={(e) =>
              setForm((p) => ({ ...p, dueDayOffset: e.target.value }))
            }
            required
          />
          <Button type="submit" loading={loading} className="w-full">
            Create Cooperative
          </Button>
        </form>
      </div>
    </div>
  );
}
