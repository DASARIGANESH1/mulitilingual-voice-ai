/**
 * AudioPlayer — a small wrapper around <audio> that auto-plays AI replies
 * and exposes a manual replay button. Releases the object URL on unmount.
 */

"use client";

import { useEffect, useRef, useState } from "react";
import { Pause, Play, Volume2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface AudioPlayerProps {
  /** Object URL pointing to the audio blob. */
  src: string;
  /** Auto-play as soon as the URL is set (default true). */
  autoPlay?: boolean;
  /** Optional label above the player. */
  label?: string;
  className?: string;
}

export function AudioPlayer({
  src,
  autoPlay = true,
  label = "AI voice reply",
  className,
}: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  // When src changes, auto-play if requested.
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !src) return;
    if (autoPlay) {
      // Catch the rejection from autoplay if the browser blocks it.
      audio.play().catch(() => {
        // Browser blocked autoplay — user can still press Play.
        setIsPlaying(false);
      });
    }
  }, [src, autoPlay]);

  // Cleanup object URL when the component unmounts OR the src changes.
  useEffect(() => {
    return () => {
      if (src.startsWith("blob:")) {
        URL.revokeObjectURL(src);
      }
    };
  }, [src]);

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) {
      audio.play().catch(() => undefined);
    } else {
      audio.pause();
    }
  };

  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-xl border border-border bg-muted/30 px-2 py-1.5 sm:px-3 sm:py-2",
        className,
      )}
    >
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-8 w-8 shrink-0 rounded-full"
        onClick={togglePlay}
        aria-label={isPlaying ? "Pause voice reply" : "Play voice reply"}
      >
        {isPlaying ? (
          <Pause className="h-4 w-4" />
        ) : (
          <Play className="h-4 w-4" />
        )}
      </Button>
      <Volume2 className="h-4 w-4 text-muted-foreground" aria-hidden />
      <span className="hidden text-xs text-muted-foreground sm:inline">
        {label}
      </span>
      <audio
        ref={audioRef}
        src={src}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
        className="hidden"
        preload="auto"
      />
      {/* Native controls as a fallback / accessibility affordance */}
      <audio src={src} controls className="h-7 flex-1 w-full sm:hidden" />
    </div>
  );
}
