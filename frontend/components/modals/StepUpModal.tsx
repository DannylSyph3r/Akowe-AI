"use client";

import { useState } from "react";
import { Lock } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { getStepUpToken } from "@/lib/api/auth";
import type { StepUpAction } from "@/lib/api/types";

const ACTION_LABELS: Record<StepUpAction, string> = {
  WITHDRAWAL: "Record Withdrawal",
  BROADCAST: "Send Broadcast",
  SETTINGS: "Update Settings",
};

interface StepUpModalProps {
  open: boolean;
  onClose: () => void;
  action: StepUpAction;
  onAuthorized: (token: string) => void;
}

export function StepUpModal({
  open,
  onClose,
  action,
  onAuthorized,
}: StepUpModalProps) {
  const [pin, setPin] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleClose = () => {
    setPin("");
    setError("");
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pin.trim()) return;

    setLoading(true);
    setError("");

    try {
      const token = await getStepUpToken(pin, action);
      handleClose();
      onAuthorized(token);
    } catch {
      setError("Incorrect PIN. Please try again.");
      setPin("");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal open={open} onClose={handleClose} title="Confirm your PIN">
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Enter your PIN to authorize:{" "}
          <span className="font-medium text-foreground">
            {ACTION_LABELS[action]}
          </span>
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="PIN"
            type="password"
            inputMode="numeric"
            maxLength={6}
            icon={<Lock className="w-4 h-4" />}
            placeholder="Enter your PIN"
            value={pin}
            onChange={(e) => {
              setPin(e.target.value.replace(/\D/g, ""));
              setError("");
            }}
            error={error}
            autoFocus
          />
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
              loading={loading}
              disabled={pin.length < 4}
              className="w-full sm:w-auto"
            >
              Confirm
            </Button>
          </div>
        </form>
      </div>
    </Modal>
  );
}
