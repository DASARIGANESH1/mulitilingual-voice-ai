/**
 * ConversationView
 *
 * Displays the conversation between the user and the AI.
 *
 * IMPORTANT:
 * - The user bubble displays the ACTUAL speech transcription returned by
 *   Groq Whisper.  The backend now rejects Whisper hallucinations such as
 *   "you", "thank you", "thanks for watching" before they ever reach this
 *   component, so the user bubble should never show a placeholder.
 * - The AI bubble displays the Gemini response and may include an audio
 *   player for the ElevenLabs TTS playback.
 */

"use client";

import { useEffect, useRef } from "react";

import {
  Bot,
  Loader2,
  User,
} from "lucide-react";

import { LanguageBadge } from "@/components/voice/LanguageBadge";

import { AudioPlayer } from "@/components/voice/AudioPlayer";

import { cn } from "@/lib/utils";

import type {
  ConversationTurn,
} from "@/types/voice";

interface ConversationViewProps {
  turns: ConversationTurn[];
  className?: string;
}

export function ConversationView({
  turns,
  className,
}: ConversationViewProps) {

  const endRef =
    useRef<HTMLDivElement | null>(null);

  /* ---------------------------------------------------------------------- */
  /* Automatically scroll to newest message                                */
  /* ---------------------------------------------------------------------- */

  useEffect(() => {

    endRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });

  }, [turns]);

  /* ---------------------------------------------------------------------- */
  /* Empty conversation                                                     */
  /* ---------------------------------------------------------------------- */

  if (turns.length === 0) {

    return (
      <div
        className={cn(
          "flex h-full min-h-[280px] flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-muted/20 p-6 text-center",
          className,
        )}
      >

        <div
          className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground"
        >

          <Bot
            className="h-6 w-6"
            aria-hidden
          />

        </div>

        <p
          className="max-w-sm text-sm text-muted-foreground"
        >
          Your conversation will appear here.
          Tap the microphone and speak in
          English, Hindi, Telugu, Tamil,
          Kannada, or any other supported
          language.
        </p>

      </div>
    );
  }

  /* ---------------------------------------------------------------------- */
  /* Conversation                                                            */
  /* ---------------------------------------------------------------------- */

  return (
    <div
      className={cn(
        "flex h-full min-h-[280px] flex-col gap-3 overflow-y-auto rounded-2xl border border-border/60 bg-background p-3 sm:p-4",
        className,
      )}
    >

      {turns.map((turn) => {

        const isUser =
          turn.role === "user";

        const messageText =
          typeof turn.content === "string"
            ? turn.content.trim()
            : "";

        return (

          <div
            key={turn.id}
            className={cn(
              "flex w-full gap-2.5",
              isUser
                ? "justify-end"
                : "justify-start",
            )}
          >

            {/* ------------------------------------------------------------ */}
            {/* AI avatar                                                    */}
            {/* ------------------------------------------------------------ */}

            {!isUser && (

              <div
                className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-white"
              >

                <Bot
                  className="h-4 w-4"
                  aria-hidden
                />

              </div>

            )}

            {/* ------------------------------------------------------------ */}
            {/* Message bubble                                               */}
            {/* ------------------------------------------------------------ */}

            <div
              className={cn(
                "max-w-[80%] rounded-2xl px-3.5 py-2.5 text-sm sm:max-w-[75%]",

                isUser
                  ? "rounded-tr-sm bg-primary text-primary-foreground"
                  : "rounded-tl-sm bg-muted text-foreground",

                turn.error &&
                  "border border-destructive/40 bg-destructive/5 text-destructive",
              )}
            >

              {/* -------------------------------------------------------- */}
              {/* AI language badge                                        */}
              {/* -------------------------------------------------------- */}

              {!isUser &&
                turn.language && (

                  <div
                    className="mb-1.5 flex justify-end"
                  >

                    <LanguageBadge
                      language={
                        turn.language
                      }
                      variant="accent"
                      showUnknown={false}
                    />

                  </div>
                )}

              {/* -------------------------------------------------------- */}
              {/* Message                                                  */}
              {/* -------------------------------------------------------- */}

              <p
                className={cn(
                  "whitespace-pre-wrap break-words leading-relaxed",
                  turn.pending &&
                    "animate-pulse text-muted-foreground",
                )}
              >

                {turn.pending ? "…" : messageText}

              </p>

              {/* -------------------------------------------------------- */}
              {/* Pending indicator                                         */}
              {/* -------------------------------------------------------- */}

              {turn.pending && (

                <span
                  className="mt-1 inline-flex items-center gap-1 text-xs text-muted-foreground"
                >

                  <Loader2
                    className="h-3 w-3 animate-spin"
                    aria-hidden
                  />

                  <span>
                    thinking…
                  </span>

                </span>
              )}

              {/* -------------------------------------------------------- */}
              {/* AI audio player                                            */}
              {/* -------------------------------------------------------- */}

              {!turn.pending &&
                turn.audioUrl &&
                !isUser && (

                  <div className="mt-2">

                    <AudioPlayer
                      src={turn.audioUrl}
                      label="AI reply"
                    />

                  </div>
                )}

            </div>

            {/* ------------------------------------------------------------ */}
            {/* User avatar                                                  */}
            {/* ------------------------------------------------------------ */}

            {isUser && (

              <div
                className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/90 text-primary-foreground"
              >

                <User
                  className="h-4 w-4"
                  aria-hidden
                />

              </div>

            )}

          </div>
        );
      })}

      <div
        ref={endRef}
      />

    </div>
  );
}
