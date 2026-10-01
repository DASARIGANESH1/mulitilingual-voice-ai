/**
 * ProviderStrip — small horizontal strip showing which providers are
 * configured on the backend. Pulled from /api/health.
 *
 * Useful for the user to instantly understand why, e.g., TTS is failing
 * (the ElevenLabs key wasn't set).
 */

"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Circle, Loader2 } from "lucide-react";
import { fetchHealth } from "@/services/voiceApi";
import type { HealthResponse } from "@/types/voice";
import { cn } from "@/lib/utils";

interface ProviderStripProps {
  className?: string;
}

export function ProviderStrip({ className }: ProviderStripProps) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchHealth()
      .then((data) => {
        if (!cancelled) setHealth(data);
      })
      .catch(() => {
        // leave health null — the strip will show "backend unreachable"
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div
        className={cn(
          "flex items-center justify-center gap-2 text-xs text-muted-foreground",
          className,
        )}
      >
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
        <span>Checking backend…</span>
      </div>
    );
  }

  if (!health) {
    return (
      <div
        className={cn(
          "flex items-center justify-center gap-1.5 rounded-full bg-amber-100 px-3 py-1 text-xs text-amber-800 dark:bg-amber-900/30 dark:text-amber-200",
          className,
        )}
      >
        <Circle className="h-3 w-3 fill-current" aria-hidden />
        <span>Backend unreachable on port 8000 — start it with: cd backend &amp;&amp; uvicorn app.main:app --port 8000 --reload</span>
      </div>
    );
  }

  const items = [
    {
      label: "STT",
      provider: health.services.stt.provider,
      configured: health.services.stt.configured,
    },
    {
      label: "LLM",
      provider: health.services.llm.provider,
      configured: health.services.llm.configured,
    },
    {
      label: "TTS",
      provider: health.services.tts.provider,
      configured: health.services.tts.configured,
    },
  ];

  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-center gap-2 text-[11px] sm:text-xs",
        className,
      )}
    >
      {items.map((it) => (
        <span
          key={it.label}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1",
            it.configured
              ? "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-200"
              : "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-200",
          )}
          title={
            it.configured
              ? `${it.label} via ${it.provider} — configured`
              : `${it.label} via ${it.provider} — not configured (add API key in backend/.env)`
          }
        >
          {it.configured ? (
            <CheckCircle2 className="h-3 w-3" aria-hidden />
          ) : (
            <Circle className="h-3 w-3 fill-current" aria-hidden />
          )}
          <span className="font-semibold">{it.label}</span>
          <span className="opacity-70">· {it.provider}</span>
        </span>
      ))}
    </div>
  );
}
