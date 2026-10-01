/**
 * Multilingual Voice AI — main page.
 *
 * Voice pipeline:
 *
 * Microphone
 *     ↓
 * MediaRecorder
 *     ↓
 * FastAPI /api/stt
 *     ↓
 * Groq Whisper
 *     ↓
 * Transcription
 *     ↓
 * Gemini /api/chat
 *     ↓
 * ElevenLabs /api/tts
 */

"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  Languages,
  RefreshCcw,
  Sparkles,
} from "lucide-react";

import { Button } from "@/components/ui/button";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import {
  ConversationView,
} from "@/components/voice/ConversationView";

import {
  ErrorBanner,
} from "@/components/voice/ErrorBanner";

import {
  LanguageBadge,
} from "@/components/voice/LanguageBadge";

import {
  MicrophoneButton,
} from "@/components/voice/MicrophoneButton";

import {
  PipelineProgress,
} from "@/components/voice/PipelineProgress";

import {
  ProviderStrip,
} from "@/components/voice/ProviderStrip";

import type {
  MicrophoneErrorCode,
} from "@/hooks/use-microphone";

import {
  chat as chatApi,
  fetchHealth,
  friendlyErrorMessage,
  synthesizeSpeech,
  transcribeAudio,
  VoiceServiceError,
} from "@/services/voiceApi";

import {
  languageLabel,
} from "@/lib/languages";

import type {
  ChatMessage,
  ConversationTurn,
  LanguageCode,
  PipelineStage,
} from "@/types/voice";

/* -------------------------------------------------------------------------- */
/* Turn ID                                                                     */
/* -------------------------------------------------------------------------- */

let turnIdCounter = 0;

function nextTurnId(): string {
  turnIdCounter += 1;

  return `turn-${Date.now()}-${turnIdCounter}`;
}

/* -------------------------------------------------------------------------- */
/* Language normalization                                                      */
/* -------------------------------------------------------------------------- */

function normalizeLanguageCode(
  value: unknown,
): LanguageCode | null {

  if (typeof value !== "string") {
    return null;
  }

  const normalized = value
    .trim()
    .toLowerCase()
    .split("-")[0]
    .split("_")[0];

  if (!normalized) {
    return null;
  }

  /*
   * Accept normal ISO-639-1 language codes.
   *
   * Examples:
   * en = English
   * hi = Hindi
   * te = Telugu
   * ta = Tamil
   * kn = Kannada
   */
  if (/^[a-z]{2}$/.test(normalized)) {
    return normalized as LanguageCode;
  }

  /*
   * Common ISO-639-3 aliases.
   */
  const aliases: Record<
    string,
    LanguageCode
  > = {
    eng: "en",
    spa: "es",
    fra: "fr",
    fre: "fr",
    deu: "de",
    ger: "de",
    ita: "it",
    por: "pt",

    hin: "hi",
    tel: "te",
    tam: "ta",
    kan: "kn",
    mal: "ml",
    ben: "bn",
    mar: "mr",
    guj: "gu",
    pan: "pa",

    ind: "id",
    msa: "ms",
    vie: "vi",
    tha: "th",

    jpn: "ja",
    kor: "ko",
    zho: "zh",
    chi: "zh",

    ara: "ar",
    rus: "ru",
    tur: "tr",

    nld: "nl",
    dut: "nl",
  };

  return aliases[normalized] ?? null;
}

/* -------------------------------------------------------------------------- */
/* Home                                                                        */
/* -------------------------------------------------------------------------- */

export default function Home() {

  /* ------------------------------------------------------------------------ */
  /* State                                                                     */
  /* ------------------------------------------------------------------------ */

  const [stage, setStage] =
    useState<PipelineStage>("idle");

  const [detectedLanguage, setDetectedLanguage] =
    useState<LanguageCode | null>(null);

  const [turns, setTurns] =
    useState<ConversationTurn[]>([]);

  const [errorMessage, setErrorMessage] =
    useState("");

  const [isRecording, setIsRecording] =
    useState(false);

  const [backendStatus, setBackendStatus] =
    useState<
      | { ok: true; providers: { stt: boolean; llm: boolean; tts: boolean } }
      | { ok: false }
      | null
    >(null);

  /* ------------------------------------------------------------------------ */
  /* Backend health check (run once on mount)                                  */
  /* ------------------------------------------------------------------------ */

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        const health = await fetchHealth();

        if (cancelled) {
          return;
        }

        setBackendStatus({
          ok: true,
          providers: {
            stt: health.services.stt.configured,
            llm: health.services.llm.configured,
            tts: health.services.tts.configured,
          },
        });
      } catch {
        if (cancelled) {
          return;
        }

        setBackendStatus({ ok: false });
      }
    }

    void check();

    return () => {
      cancelled = true;
    };
  }, []);

  /* ------------------------------------------------------------------------ */
  /* Conversation history                                                      */
  /* ------------------------------------------------------------------------ */

  const historyRef =
    useRef<ChatMessage[]>([]);

  /* ------------------------------------------------------------------------ */
  /* Pipeline busy                                                             */
  /* ------------------------------------------------------------------------ */

  const isPipelineBusy =
    stage === "transcribing" ||
    stage === "thinking" ||
    stage === "generating" ||
    stage === "speaking";

  /* ------------------------------------------------------------------------ */
  /* Microphone errors                                                         */
  /* ------------------------------------------------------------------------ */

  const handleMicError = useCallback(
    (
      code: MicrophoneErrorCode,
      message: string,
    ) => {

      const friendlyMap: Record<
        MicrophoneErrorCode,
        string
      > = {

        mic_not_supported:
          "Your browser doesn't support microphone capture. Try Chrome or Edge.",

        mic_permission_denied:
          "Microphone permission was denied. Allow microphone access and try again.",

        mic_no_device:
          "No microphone was found on this device.",

        mic_start_failed:
          "Couldn't start the microphone. " + message,

        mic_data_unavailable:
          "No audio was captured. Check your microphone and try again.",
      };

      setErrorMessage(
        friendlyMap[code] ?? message,
      );

      setStage("error");
    },
    [],
  );

  /* ------------------------------------------------------------------------ */
  /* Service errors                                                            */
  /* ------------------------------------------------------------------------ */

  const handleServiceError = useCallback(
    (
      err: unknown,
      fallback: string,
    ) => {

      if (err instanceof VoiceServiceError) {

        setErrorMessage(
          friendlyErrorMessage(
            err.code,
            err.message,
          ),
        );

      } else if (err instanceof Error) {

        setErrorMessage(
          err.message || fallback,
        );

      } else {

        setErrorMessage(
          friendlyErrorMessage(
            "network_error",
            fallback,
          ),
        );
      }

      setStage("error");
    },
    [],
  );

  /* ======================================================================== */
  /* MAIN VOICE PIPELINE                                                      */
  /* ======================================================================== */

  const runPipeline = useCallback(
    async (audioBlob: Blob) => {

      /* -------------------------------------------------------------------- */
      /* Reset errors                                                          */
      /* -------------------------------------------------------------------- */

      setErrorMessage("");

      /* -------------------------------------------------------------------- */
      /* Validate audio                                                        */
      /* -------------------------------------------------------------------- */

      if (
        !audioBlob ||
        audioBlob.size === 0
      ) {

        setErrorMessage(
          "No audio was captured. Please speak again.",
        );

        setStage("error");

        return;
      }

      console.log(
        "================================================",
      );

      console.log(
        "VOICE PIPELINE START",
      );

      console.log(
        "Audio MIME:",
        audioBlob.type,
      );

      console.log(
        "Audio size:",
        audioBlob.size,
        "bytes",
      );

      console.log(
        "================================================",
      );

      /* -------------------------------------------------------------------- */
      /* Create user conversation turn                                        */
      /* -------------------------------------------------------------------- */

      const userTurnId =
        nextTurnId();

      const userPlaceholder:
        ConversationTurn = {
          id: userTurnId,
          role: "user",
          content: "",
          pending: true,
        };

      setTurns(
        (previous) => [
          ...previous,
          userPlaceholder,
        ],
      );

      /* -------------------------------------------------------------------- */
      /* STAGE 1 — SPEECH TO TEXT                                             */
      /* -------------------------------------------------------------------- */

      setStage("transcribing");

      let userText = "";

      let languageCode:
        LanguageCode | null = null;

      try {

        console.log(
          "STT: Sending recorded audio...",
        );

        const sttResult =
          await transcribeAudio(
            audioBlob,
          );

        /* ---------------------------------------------------------------- */
        /* IMPORTANT — actual Groq result                                   */
        /* ---------------------------------------------------------------- */

        console.log(
          "================================================",
        );

        console.log(
          "GROQ STT RESULT",
        );

        console.log(
          "Raw transcript:",
          sttResult.text,
        );

        console.log(
          "Detected language:",
          sttResult.language,
        );

        console.log(
          "Language confidence:",
          sttResult.language_confidence,
        );

        console.log(
          "================================================",
        );

        /* ---------------------------------------------------------------- */
        /* Extract transcript                                                */
        /* ---------------------------------------------------------------- */

        userText =
          typeof sttResult.text ===
          "string"
            ? sttResult.text.trim()
            : "";

        const normalisedUserText =
          userText
            .replace(/[\s\u00A0]+/g, " ")
            .trim();

        const transcriptGuard =
          normalisedUserText
            .replace(/[.?!,;:]/g, "")
            .trim()
            .toLowerCase();

        if (
          !normalisedUserText ||
          transcriptGuard === "you" ||
          transcriptGuard === "user"
        ) {
          throw new Error(
            "STT returned an invalid placeholder transcript instead of the actual spoken words.",
          );
        }

        userText = normalisedUserText;

        /* ---------------------------------------------------------------- */
        /* Normalize detected language                                      */
        /* ---------------------------------------------------------------- */

        const normalizedLanguage =
          normalizeLanguageCode(
            sttResult.language,
          );

        if (normalizedLanguage) {
          languageCode = normalizedLanguage;
          setDetectedLanguage(languageCode);
        } else if (sttResult.language) {
          console.warn(
            "STT returned a non-standard language code; preserving raw value for debugging:",
            sttResult.language,
          );
          languageCode = normalizeLanguageCode("en") ?? "en";
        } else {
          languageCode = "en";
        }

        /* ---------------------------------------------------------------- */
        /* VERY IMPORTANT DEBUG                                             */
        /* ---------------------------------------------------------------- */

        console.log(
          "FINAL USER TEXT:",
          userText,
        );

        console.log(
          "FINAL USER LANGUAGE:",
          languageCode,
        );

      } catch (err) {

        setTurns(
          (previous) =>
            previous.map(
              (turn) =>
                turn.id === userTurnId
                  ? {
                      ...turn,
                      pending: false,
                      error: true,
                      content:
                        "(transcription failed)",
                    }
                  : turn,
            ),
        );

        handleServiceError(
          err,
          "Speech recognition failed. Please speak clearly and try again.",
        );

        return;
      }

      /* -------------------------------------------------------------------- */
      /* UPDATE USER TURN WITH REAL TEXT                                      */
      /* -------------------------------------------------------------------- */

      setTurns(
        (previous) =>
          previous.map(
            (turn) =>
              turn.id === userTurnId
                ? {
                    ...turn,
                    pending: false,

                    /*
                     * THIS MUST BE THE ACTUAL
                     * TRANSCRIPTION.
                     */
                    content: userText,

                    language:
                      languageCode,
                  }
                : turn,
          ),
      );

      console.log(
        "Conversation user content:",
        userText,
      );

      /* -------------------------------------------------------------------- */
      /* History snapshot                                                      */
      /* -------------------------------------------------------------------- */

      const historySnapshot =
        [
          ...historyRef.current,
        ];

      const chatLanguage =
        languageCode ?? "en";

      /* -------------------------------------------------------------------- */
      /* STAGE 2 — GEMINI                                                     */
      /* -------------------------------------------------------------------- */

      setStage("thinking");

      const aiTurnId =
        nextTurnId();

      const aiPlaceholder:
        ConversationTurn = {
          id: aiTurnId,
          role: "assistant",
          content: "",
          pending: true,
          language: languageCode,
        };

      setTurns(
        (previous) => [
          ...previous,
          aiPlaceholder,
        ],
      );

      let aiText = "";

      try {

        console.log(
          "================================================",
        );

        console.log(
          "GEMINI REQUEST",
        );

        console.log(
          "Message being sent:",
          userText,
        );

        console.log(
          "Language:",
          languageCode,
        );

        console.log(
          "History:",
          historySnapshot,
        );

        console.log(
          "================================================",
        );

        const chatResult =
          await chatApi(
            userText,
            chatLanguage,
            historySnapshot,
          );

        aiText =
          typeof chatResult.response ===
          "string"
            ? chatResult.response.trim()
            : "";

        if (!aiText) {

          throw new Error(
            "Gemini returned an empty response.",
          );
        }

        console.log(
          "Gemini response:",
          aiText,
        );

      } catch (err) {

        setTurns(
          (previous) =>
            previous.map(
              (turn) =>
                turn.id === aiTurnId
                  ? {
                      ...turn,
                      pending: false,
                      error: true,
                      content:
                        "(no reply)",
                    }
                  : turn,
            ),
        );

        handleServiceError(
          err,
          "I couldn't generate a reply. Please try again.",
        );

        return;
      }

      /* -------------------------------------------------------------------- */
      /* Update assistant turn                                                 */
      /* -------------------------------------------------------------------- */

      setTurns(
        (previous) =>
          previous.map(
            (turn) =>
              turn.id === aiTurnId
                ? {
                    ...turn,
                    pending: false,
                    content: aiText,
                    language:
                      languageCode,
                  }
                : turn,
          ),
      );

      /* -------------------------------------------------------------------- */
      /* Update history                                                        */
      /* -------------------------------------------------------------------- */

      const updatedHistory:
        ChatMessage[] = [
          ...historySnapshot,

          {
            role: "user",
            content: userText,
          },

          {
            role: "assistant",
            content: aiText,
          },
        ];

      historyRef.current =
        updatedHistory.slice(-20);

      /* -------------------------------------------------------------------- */
      /* STAGE 3 — ELEVENLABS TTS                                             */
      /* -------------------------------------------------------------------- */

      setStage("speaking");

      try {

        console.log(
          "Generating voice response...",
        );

        const {
          audioUrl,
        } =
          await synthesizeSpeech(
            aiText,
            chatLanguage,
          );

        setTurns(
          (previous) =>
            previous.map(
              (turn) =>
                turn.id === aiTurnId
                  ? {
                      ...turn,
                      audioUrl,
                    }
                  : turn,
            ),
        );

      } catch (err) {

        const message =
          err instanceof VoiceServiceError
            ? friendlyErrorMessage(
                err.code,
                err.message,
              )
            : "Voice generation failed. Your text reply is still visible.";

        setErrorMessage(
          message,
        );

        setStage("done");

        return;
      }

      /* -------------------------------------------------------------------- */
      /* COMPLETE                                                              */
      /* -------------------------------------------------------------------- */

      setStage("done");

      console.log(
        "================================================",
      );

      console.log(
        "VOICE PIPELINE COMPLETE",
      );

      console.log(
        "User:",
        userText,
      );

      console.log(
        "Assistant:",
        aiText,
      );

      console.log(
        "================================================",
      );
    },
    [handleServiceError],
  );

  /* ------------------------------------------------------------------------ */
  /* Clear conversation                                                        */
  /* ------------------------------------------------------------------------ */

  const handleClear =
    useCallback(() => {

      setTurns([]);

      historyRef.current = [];

      setDetectedLanguage(null);

      setErrorMessage("");

      setStage("idle");

      setIsRecording(false);

    }, []);

  /* ------------------------------------------------------------------------ */
  /* Dismiss error                                                             */
  /* ------------------------------------------------------------------------ */

  const handleDismissError =
    useCallback(() => {

      setErrorMessage("");

      setStage("idle");

    }, []);

  /* ------------------------------------------------------------------------ */
  /* Displayed stage                                                           */
  /* ------------------------------------------------------------------------ */

  const displayedStage:
    PipelineStage =
    useMemo(() => {

      if (isRecording) {
        return "recording";
      }

      return stage;

    }, [
      isRecording,
      stage,
    ]);

  /* ======================================================================== */
  /* UI                                                                        */
  /* ======================================================================== */

  return (
    <main className="flex min-h-screen flex-col bg-gradient-to-b from-background to-muted/30">

      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-5 px-4 py-6 sm:px-6 sm:py-10">

        {/* ---------------------------------------------------------------- */}
        {/* Header                                                            */}
        {/* ---------------------------------------------------------------- */}

        <header className="flex flex-col items-center gap-3 text-center">

          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">

            <Sparkles
              className="h-3.5 w-3.5"
              aria-hidden
            />

            Multilingual Voice AI

          </div>

          <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            Speak in your language. Get a human-like reply.
          </h1>

          <p className="max-w-xl text-sm text-muted-foreground sm:text-base">
            Real speech-to-text (Groq Whisper),
            Gemini conversation, and ElevenLabs
            multilingual voice generation.
          </p>

          <ProviderStrip
            className="mt-1"
          />

        </header>

        {/* ---------------------------------------------------------------- */}
        {/* Backend status banner                                            */}
        {/* ---------------------------------------------------------------- */}

        {backendStatus && !backendStatus.ok && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-200">
            Backend unavailable. Please start the FastAPI server on port 8000
            (<code className="rounded bg-amber-100 px-1 py-0.5 dark:bg-amber-900/50">cd backend &amp;&amp; python run.py</code>).
          </div>
        )}

        {backendStatus && backendStatus.ok && (
          !(backendStatus.providers.stt && backendStatus.providers.llm && backendStatus.providers.tts)
        ) && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-200">
            Backend is reachable but some API keys are missing in
            <code className="mx-1 rounded bg-amber-100 px-1 py-0.5 dark:bg-amber-900/50">backend/.env</code>.
            Missing: {[
              !backendStatus.providers.stt && "GROQ_API_KEY",
              !backendStatus.providers.llm && "GEMINI_API_KEY",
              !backendStatus.providers.tts && "ELEVENLABS_API_KEY / VOICE_ID",
            ].filter(Boolean).join(", ")}.
          </div>
        )}

        {/* ---------------------------------------------------------------- */}
        {/* Detected language                                                */}
        {/* ---------------------------------------------------------------- */}

        <div className="flex items-center justify-between gap-2">

          <div className="flex items-center gap-2 text-sm text-muted-foreground">

            <Languages
              className="h-4 w-4"
              aria-hidden
            />

            <span>
              Detected language:
            </span>

            <LanguageBadge
              language={
                detectedLanguage
              }
              variant={
                detectedLanguage
                  ? "accent"
                  : "neutral"
              }
            />

            {detectedLanguage && (
              <span className="text-xs text-muted-foreground">
                (
                {languageLabel(
                  detectedLanguage,
                )}
                )
              </span>
            )}

          </div>

          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="gap-1.5 text-muted-foreground"
            onClick={handleClear}
            disabled={
              turns.length === 0 &&
              stage === "idle"
            }
            aria-label="Clear conversation"
          >

            <RefreshCcw
              className="h-3.5 w-3.5"
              aria-hidden
            />

            <span className="hidden sm:inline">
              Clear
            </span>

          </Button>

        </div>

        {/* ---------------------------------------------------------------- */}
        {/* Pipeline                                                         */}
        {/* ---------------------------------------------------------------- */}

        <PipelineProgress
          stage={displayedStage}
        />

        {/* ---------------------------------------------------------------- */}
        {/* Error                                                             */}
        {/* ---------------------------------------------------------------- */}

        {errorMessage && (
          <ErrorBanner
            message={errorMessage}
            onDismiss={
              handleDismissError
            }
          />
        )}

        {/* ---------------------------------------------------------------- */}
        {/* Conversation                                                     */}
        {/* ---------------------------------------------------------------- */}

        <Card className="flex-1">

          <CardHeader className="border-b border-border/60 bg-muted/30 py-3">

            <CardTitle className="text-sm font-semibold text-foreground">
              Conversation
            </CardTitle>

          </CardHeader>

          <CardContent className="p-0">

            <ConversationView
              turns={turns}
              className="rounded-b-xl border-0"
            />

          </CardContent>

        </Card>

        {/* ---------------------------------------------------------------- */}
        {/* Microphone                                                       */}
        {/* ---------------------------------------------------------------- */}

        <div className="flex flex-col items-center gap-3 pt-1 pb-2">

          <MicrophoneButton
            onAudioCaptured={(blob) => {
              void runPipeline(blob);
            }}
            onError={handleMicError}
            onRecordingChange={
              setIsRecording
            }
            disabled={
              isPipelineBusy
            }
          />

          <p className="text-center text-xs text-muted-foreground sm:text-sm">
            Click the mic, speak in any
            supported language, then click
            again to stop.
          </p>

        </div>

        {/* ---------------------------------------------------------------- */}
        {/* Footer                                                           */}
        {/* ---------------------------------------------------------------- */}

        <footer className="mt-auto pt-4 text-center text-[11px] text-muted-foreground">

          <p>
            Backend: FastAPI on port 8000 ·
            STT Groq Whisper · LLM Google
            Gemini · TTS ElevenLabs · API
            keys remain server-side in
            <code className="mx-1 rounded bg-muted px-1 py-0.5">
              backend/.env
            </code>
          </p>

        </footer>

      </div>

    </main>
  );
}