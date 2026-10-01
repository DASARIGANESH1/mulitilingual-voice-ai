/**
 * MicrophoneButton — the main record button.
 *
 * Behaviour:
 *   - Click to start recording; click again (or release) to stop.
 *   - While recording, an animated ring pulses around the icon and the
 *     elapsed time is shown below.
 *   - When a backend stage is active (transcribing / thinking / speaking)
 *     the button is disabled and shows a spinner.
 *   - Permission requests surface as a "Requesting mic…" state.
 *   - Errors raised by the useMicrophone hook bubble up via the
 *     `onError` callback so the parent can render an ErrorBanner.
 */

"use client";

import { useEffect } from "react";
import { Loader2, Mic, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useMicrophone } from "@/hooks/use-microphone";
import type { MicrophoneErrorCode } from "@/hooks/use-microphone";

interface MicrophoneButtonProps {
  /** Fired whenever the recording stops with a non-empty Blob. */
  onAudioCaptured: (blob: Blob) => void;
  /** Fired when any microphone error occurs. */
  onError: (code: MicrophoneErrorCode, message: string) => void;
  /** Fired whenever the recording state changes (so the parent can
   * drive the pipeline-progress UI). */
  onRecordingChange?: (isRecording: boolean) => void;
  /** Disable the button (e.g. while the pipeline is running). */
  disabled?: boolean;
  /** Optional className override. */
  className?: string;
}

function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

export function MicrophoneButton({
  onAudioCaptured,
  onError,
  onRecordingChange,
  disabled = false,
  className,
}: MicrophoneButtonProps) {
  const mic = useMicrophone();

  // Surface any microphone errors to the parent so it can render the
  // ErrorBanner uniformly across the pipeline.
  useEffect(() => {
    if (mic.errorCode && mic.errorMessage) {
      onError(mic.errorCode, mic.errorMessage);
    }
  }, [mic.errorCode, mic.errorMessage, onError]);

  // Surface the recording state to the parent so it can drive the
  // pipeline-progress UI without needing a second hook instance.
  useEffect(() => {
    onRecordingChange?.(mic.isRecording);
  }, [mic.isRecording, onRecordingChange]);

  const handleClick = async () => {
    if (mic.isRecording) {
      const blob = await mic.stopRecording();
      if (blob && blob.size > 0) {
        onAudioCaptured(blob);
      }
    } else {
      await mic.startRecording();
    }
  };

  const isBusy =
    disabled || mic.requestingPermission;
  const isRecording = mic.isRecording;

  // We deliberately use a large hit area — at least 80px on mobile —
  // because the user is tapping it while speaking and a small target
  // leads to mid-recording stop errors.
  return (
    <div
    className={cn(
        "flex flex-col items-center gap-2",
        className,
      )}
    >
      <div className="relative">
        {/* Animated pulsing rings while recording. */}
        {isRecording && (
          <>
            <span
              className="absolute inset-0 animate-ping rounded-full bg-rose-400/50"
              aria-hidden
            />
            <span
              className="absolute -inset-2 animate-pulse rounded-full border-2 border-rose-500/60"
              aria-hidden
            />
          </>
        )}
        <Button
          type="button"
          onClick={handleClick}
          disabled={isBusy}
          aria-pressed={isRecording}
          aria-label={isRecording ? "Stop recording" : "Start recording"}
          className={cn(
            "relative z-10 flex h-20 w-20 items-center justify-center rounded-full shadow-lg transition-all sm:h-24 sm:w-24",
            isRecording
              ? "bg-rose-600 hover:bg-rose-700 text-white"
              : "bg-emerald-600 hover:bg-emerald-700 text-white",
            isBusy && "opacity-80",
          )}
        >
          {isBusy ? (
            <Loader2 className="h-8 w-8 animate-spin" aria-hidden />
          ) : isRecording ? (
            <Square className="h-7 w-7 fill-current" aria-hidden />
          ) : (
            <Mic className="h-8 w-8" aria-hidden />
          )}
        </Button>
      </div>

      <div className="text-center text-xs text-muted-foreground sm:text-sm">
        {isRecording ? (
          <span className="font-mono tabular-nums text-rose-600 dark:text-rose-400">
            ● {formatDuration(mic.durationSec)}
          </span>
        ) : mic.requestingPermission ? (
          <span>Requesting mic permission…</span>
        ) : (
          <span>
            {disabled ? "Pipeline running…" : "Click to speak"}
          </span>
        )}
      </div>
    </div>
  );
}
