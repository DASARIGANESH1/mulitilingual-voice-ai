/**
 * ErrorBanner — friendly inline error display.
 * Used to show the most recent backend / microphone error.
 */

"use client";

import { AlertTriangle, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ErrorBannerProps {
  message: string;
  onDismiss?: () => void;
  className?: string;
}

export function ErrorBanner({ message, onDismiss, className }: ErrorBannerProps) {
  if (!message) return null;

  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-3 rounded-xl border border-destructive/30 bg-destructive/5 px-3 py-2.5 text-sm text-destructive sm:px-4 sm:py-3",
        className,
      )}
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <p className="flex-1 leading-relaxed">{message}</p>
      {onDismiss && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-6 w-6 shrink-0 text-destructive hover:bg-destructive/10 hover:text-destructive"
          onClick={onDismiss}
          aria-label="Dismiss error"
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      )}
    </div>
  );
}
