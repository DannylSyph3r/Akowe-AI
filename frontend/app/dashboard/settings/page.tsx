"use client";

import { useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Info } from "lucide-react";
import { useCoop } from "@/context/CoopContext";
import { getCooperative, updateSettings } from "@/lib/api/cooperatives";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { StepUpModal } from "@/components/modals/StepUpModal";

const FREQUENCY_OPTIONS = [
  { value: "weekly", label: "Weekly" },
  { value: "biweekly", label: "Bi-weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "bimonthly", label: "Bi-monthly" },
  { value: "quarterly", label: "Quarterly" },
  { value: "biannual", label: "Bi-annual" },
  { value: "annual", label: "Annual" },
];

export default function SettingsPage() {
  const { activeCoop } = useCoop();
  const coopId = activeCoop?.id ?? "";
  const queryClient = useQueryClient();

  const { data: coop } = useQuery({
    queryKey: ["coop", coopId, "detail"],
    queryFn: () => getCooperative(coopId),
    enabled: !!coopId,
  });

  const [form, setForm] = useState({
    contributionAmountNaira: "",
    frequency: "monthly",
    dueDayOffset: "3",
  });
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!coop) return;
    setForm({
      contributionAmountNaira: String(coop.contribution_amount_kobo / 100),
      frequency: coop.current_schedule.frequency,
      dueDayOffset: String(coop.current_schedule.due_day_offset),
    });
  }, [coop]);

  const handleAuthorized = async (stepUpToken: string) => {
    setSubmitting(true);
    try {
      await updateSettings(
        coopId,
        {
          contribution_amount_kobo: Math.round(
            parseFloat(form.contributionAmountNaira) * 100,
          ),
          frequency: form.frequency,
          due_day_offset: parseInt(form.dueDayOffset, 10),
        },
        stepUpToken,
      );
      toast.success("Settings updated");
      queryClient.invalidateQueries({ queryKey: ["coop", coopId, "detail"] });
    } catch (err: any) {
      toast.error(err?.response?.data?.message ?? "Failed to update settings");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-lg space-y-6">
      <h1 className="text-xl font-semibold text-foreground">Settings</h1>

      <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-800">
        <Info className="w-4 h-4 shrink-0 mt-0.5" />
        Changes to contribution amount and frequency take effect from the next
        period onwards.
      </div>

      <div className="bg-white rounded-xl border border-border p-6 space-y-4">
        <Input
          label="Contribution Amount (₦)"
          type="number"
          min="1"
          value={form.contributionAmountNaira}
          onChange={(e) =>
            setForm((p) => ({
              ...p,
              contributionAmountNaira: e.target.value,
            }))
          }
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
          label="Due Day Offset (days)"
          type="number"
          min="0"
          max="60"
          value={form.dueDayOffset}
          onChange={(e) =>
            setForm((p) => ({ ...p, dueDayOffset: e.target.value }))
          }
        />
        <Button
          onClick={() => setStepUpOpen(true)}
          loading={submitting}
          className="w-full"
        >
          Save Changes
        </Button>
      </div>

      <StepUpModal
        open={stepUpOpen}
        onClose={() => setStepUpOpen(false)}
        action="SETTINGS"
        onAuthorized={handleAuthorized}
      />
    </div>
  );
}
