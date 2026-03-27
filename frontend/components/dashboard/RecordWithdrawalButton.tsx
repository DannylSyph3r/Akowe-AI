"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowDownCircle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { StepUpModal } from "@/components/modals/StepUpModal";
import { WithdrawalModal } from "@/components/modals/WithdrawalModal";
import { cn } from "@/lib/utils";

interface RecordWithdrawalButtonProps {
  coopId: string;
  className?: string;
}

export function RecordWithdrawalButton({
  coopId,
  className,
}: RecordWithdrawalButtonProps) {
  const queryClient = useQueryClient();
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [withdrawalOpen, setWithdrawalOpen] = useState(false);
  const [stepUpToken, setStepUpToken] = useState("");

  const handleAuthorized = (token: string) => {
    setStepUpToken(token);
    setWithdrawalOpen(true);
  };

  const handleSuccess = () => {
    queryClient.invalidateQueries({ queryKey: ["coop", coopId, "detail"] });
    queryClient.invalidateQueries({
      queryKey: ["coop", coopId, "withdrawals"],
    });
  };

  return (
    <>
      <Button
        variant="outline"
        onClick={() => setStepUpOpen(true)}
        className={cn(className)}
      >
        <ArrowDownCircle className="w-4 h-4" />
        Record Withdrawal
      </Button>

      <StepUpModal
        open={stepUpOpen}
        onClose={() => setStepUpOpen(false)}
        action="WITHDRAWAL"
        onAuthorized={handleAuthorized}
      />

      <WithdrawalModal
        open={withdrawalOpen}
        onClose={() => setWithdrawalOpen(false)}
        coopId={coopId}
        stepUpToken={stepUpToken}
        onSuccess={handleSuccess}
      />
    </>
  );
}
