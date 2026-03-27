"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Radio } from "lucide-react";
import { useCoop } from "@/context/CoopContext";
import { getMembers, broadcastMessage } from "@/lib/api/cooperatives";
import { Button } from "@/components/ui/Button";
import { StepUpModal } from "@/components/modals/StepUpModal";
import type { ApiError } from "@/lib/api/client";

export default function BroadcastPage() {
  const { activeCoop } = useCoop();
  const coopId = activeCoop?.id ?? "";

  const { data: members = [] } = useQuery({
    queryKey: ["coop", coopId, "members"],
    queryFn: () => getMembers(coopId),
    enabled: !!coopId,
  });

  const [message, setMessage] = useState("");
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSend = () => {
    if (!message.trim()) {
      toast.error("Please enter a message");
      return;
    }
    setStepUpOpen(true);
  };

  const handleAuthorized = async (stepUpToken: string) => {
    setSubmitting(true);
    try {
      const result = await broadcastMessage(
        coopId,
        message.trim(),
        stepUpToken,
      );
      toast.success(`Message sent to ${result.sent_to} member(s)`);
      setMessage("");
    } catch (err) {
      const apiError = err as ApiError;
      toast.error(apiError.response?.data?.message ?? "Broadcast failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl space-y-5 sm:space-y-6">
      <h1 className="text-xl font-semibold text-foreground">Broadcast</h1>

      <div className="space-y-4 rounded-xl border border-border bg-white p-4 sm:p-6">
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-foreground">Message</label>
          <textarea
            className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm
                       text-foreground placeholder:text-muted-foreground resize-none
                       focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary
                       transition-colors"
            rows={5}
            maxLength={1000}
            placeholder="Type the message to send to all members via WhatsApp…"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
          />
          <p className="text-xs text-muted-foreground text-right">
            {message.length}/1000
          </p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted-foreground">
            <span className="font-medium text-foreground">
              {members.length}
            </span>{" "}
            member(s) will receive this
          </p>
          <Button
            onClick={handleSend}
            loading={submitting}
            disabled={!message.trim()}
            className="w-full sm:w-auto"
          >
            <Radio className="w-4 h-4" />
            Send Broadcast
          </Button>
        </div>
      </div>

      <StepUpModal
        open={stepUpOpen}
        onClose={() => setStepUpOpen(false)}
        action="BROADCAST"
        onAuthorized={handleAuthorized}
      />
    </div>
  );
}
