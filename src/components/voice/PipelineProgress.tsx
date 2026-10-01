/**
 * PipelineProgress — visualises the current stage of the voice pipeline.
 *
 * Each stage corresponds to a real backend operation:
 *   recording     → MediaRecorder is running in the browser
 *   transcribing  → POST /api/stt in flight
 *   thinking      → POST /api/chat in flight
 *   generating    → response parsed, ready to display
 *   speaking      → POST /api/tts in flight (and audio is being played back)
 *   done          → pipeline finished, waiting for the next user turn
 *   error         → any stage failed
 */

"use client";

import { Check, Loader2, Mic, MessageSquare, Volume2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { PipelineStage } from "@/types/voice";

interface PipelineProgressProps {
  stage: PipelineStage;
  className?: string;
}

interface Step {
  key: PipelineStage;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const STEPS: Step[] = [
  { key: "recording", label: "Listening", icon: Mic },
  { key: "transcribing", label: "Transcribing", icon: MessageSquare },
  { key: "thinking", label: "Thinking", icon: Loader2 },
  { key: "speaking", label: "Speaking", icon: Volume2 },
];

export function PipelineProgress({ stage, className }: PipelineProgressProps) {
  // Determine the active step index from the current stage.
  const activeIndex =
    stage === "done"
      ? STEPS.length // past the last step
      : STEPS.findIndex((s) => s.key === stage);

  const isError = stage === "error";
  const isIdle = stage === "idle";

  if (isIdle) return null;

  return (
    <div
      className={cn(
        "flex w-full items-center justify-between gap-1 rounded-2xl border border-border/60 bg-muted/40 px-2 py-3 sm:px-4 sm:py-4",
        className,
      )}
      role="status"
      aria-live="polite"
    >
      {STEPS.map((step, idx) => {
        const isDone = idx < activeIndex;
        const isActive = idx === activeIndex;
        const StepIcon = step.icon;
        return (
          <div
            key={step.key}
            className="flex flex-1 flex-col items-center gap-1.5 text-center"
          >
            <div className="flex w-full items-center">
              {idx > 0 && (
                <div
                  className={cn(
                    "h-0.5 flex-1 rounded-full transition-colors",
                    idx <= activeIndex
                      ? "bg-emerald-500"
                      : "bg-border",
                  )}
                />
              )}
              <div
                className={cn(
                  "flex h-9 w-9 items-center justify-center rounded-full border text-sm transition-all sm:h-10 sm:w-10",
                  isActive && !isError && "border-emerald-500 bg-emerald-500 text-white",
                  isActive && isError && "border-destructive bg-destructive text-destructive-foreground",
                  isDone && "border-emerald-500 bg-emerald-500/10 text-emerald-600",
                  !isActive && !isDone && !isError && "border-border bg-background text-muted-foreground",
                )}
              >
                {isDone ? (
                  <Check className="h-4 w-4" aria-hidden />
                ) : (
                  <StepIcon
                    className={cn(
                      "h-4 w-4",
                      isActive && step.key !== "thinking" && "animate-pulse",
                      step.key === "thinking" && isActive && "animate-spin",
                    )}
                    aria-hidden
                  />
                )}
              </div>
              {idx < STEPS.length - 1 && (
                <div
                  className={cn(
                    "h-0.5 flex-1 rounded-full transition-colors",
                    idx < activeIndex ? "bg-emerald-500" : "bg-border",
                  )}
                />
              )}
            </div>
            <span
              className={cn(
                "text-[10px] font-medium uppercase tracking-wide sm:text-xs",
                isActive ? "text-foreground" : "text-muted-foreground",
              )}
            >
              {step.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}
