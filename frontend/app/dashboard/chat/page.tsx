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
    <div className="flex flex-col h-[calc(100vh-3.5rem-3rem)]">
      <div className="mb-4 shrink-0">
        <h1 className="text-xl font-semibold text-foreground">
          AI Financial Advisor
        </h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Ask anything about your cooperative's finances
        </p>
      </div>
      <div className="flex-1 bg-white rounded-xl border border-border overflow-hidden min-h-0">
        {/*
          Key on activeCoop.id ensures full remount on coop switch.
          This clears message history and prevents context bleed between cooperatives.
        */}
        <ChatWidget key={activeCoop.id} coopId={activeCoop.id} />
      </div>
    </div>
  );
}
