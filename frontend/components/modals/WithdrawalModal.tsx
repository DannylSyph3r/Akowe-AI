"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { recordWithdrawal } from "@/lib/api/cooperatives";
import type { ApiError } from "@/lib/api/client";

interface WithdrawalModalProps {
  open: boolean;
  onClose: () => void;
  coopId: string;
  stepUpToken: string;
  onSuccess: () => void;
}

export function WithdrawalModal({
  open,
  onClose,
  coopId,
  stepUpToken,
  onSuccess,
}: WithdrawalModalProps) {
  const [amountNaira, setAmountNaira] = useState("");
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);

  const handleClose = () => {
    setAmountNaira("");
    setReason("");
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const amount = parseFloat(amountNaira);
    if (!amount || amount <= 0 || !reason.trim()) return;

    setLoading(true);
    try {
      await recordWithdrawal(
        coopId,
        { amount_kobo: Math.round(amount * 100), reason: reason.trim() },
        stepUpToken,
      );
      toast.success("Withdrawal recorded successfully");
      onSuccess();
      handleClose();
    } catch (err) {
      const apiError = err as ApiError;
      toast.error(
        apiError.response?.data?.message ?? "Failed to record withdrawal",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal open={open} onClose={handleClose} title="Record Withdrawal">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Amount (₦)"
          type="number"
          min="1"
          step="1"
          placeholder="e.g. 50000"
          value={amountNaira}
          onChange={(e) => setAmountNaira(e.target.value)}
          required
        />
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-foreground">Reason</label>
          <textarea
            className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm
                       text-foreground placeholder:text-muted-foreground resize-none
                       focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary
                       transition-colors"
            rows={3}
            maxLength={500}
            placeholder="Describe the reason for this withdrawal"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            required
          />
        </div>
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button
            variant="ghost"
            type="button"
            onClick={handleClose}
            className="w-full sm:w-auto"
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="destructive"
            loading={loading}
            disabled={!amountNaira || !reason.trim()}
            className="w-full sm:w-auto"
          >
            Record Withdrawal
          </Button>
        </div>
      </form>
    </Modal>
  );
}
