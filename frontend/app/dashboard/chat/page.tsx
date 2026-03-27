"use client";

import { useCoop } from "@/context/CoopContext";
import { ChatWidget } from "@/components/ChatWidget";

export default function ChatPage() {
  const { activeCoop } = useCoop();

  if (!activeCoop) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
        Select a cooperative to start chatting.
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div className="shrink-0">
        <h1 className="text-xl font-semibold text-foreground">
          AI Financial Advisor
        </h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Ask anything about your cooperative&apos;s finances
        </p>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden rounded-xl border border-border bg-white">
        {/*
          Key on activeCoop.id ensures full remount on coop switch.
          This clears message history and prevents context bleed between cooperatives.
        */}
        <ChatWidget key={activeCoop.id} coopId={activeCoop.id} />
      </div>
    </div>
  );
}
