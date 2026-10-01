/**
 * LanguageBadge — a small pill that shows the detected / active language.
 */

"use client";

import { Badge } from "@/components/ui/badge";
import { languageFlag, languageLabel } from "@/lib/languages";
import type { LanguageCode } from "@/types/voice";
import { cn } from "@/lib/utils";

interface LanguageBadgeProps {
  language: LanguageCode | null | undefined;
  variant?: "neutral" | "accent";
  showUnknown?: boolean;
  className?: string;
}

export function LanguageBadge({
  language,
  variant = "neutral",
  showUnknown = true,
  className,
}: LanguageBadgeProps) {
  const label = languageLabel(language);
  const flag = languageFlag(language);

  if (!language && !showUnknown) {
    return null;
  }

  return (
    <Badge
      variant="secondary"
      className={cn(
        "gap-1.5 font-medium",
        variant === "accent" &&
          "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/30 dark:text-emerald-200",
        className,
      )}
      aria-label={`Detected language: ${label}`}
    >
      <span aria-hidden className="text-base leading-none">
        {flag}
      </span>
      <span className="uppercase tracking-wide text-[11px] font-semibold">
        {label}
      </span>
    </Badge>
  );
}
