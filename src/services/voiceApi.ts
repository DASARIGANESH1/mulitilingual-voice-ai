/**
 * Voice API service — frontend ↔ FastAPI backend.
 *
 * Handles:
 * - Speech-to-Text
 * - Chat / Gemini
 * - Text-to-Speech
 * - Backend health
 * - Supported languages
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

import type {
  ChatMessage,
  ChatResponse,
  HealthResponse,
  LanguagesResponse,
  STTResponse,
  TTSResponse,
  VoiceApiError,
  VoiceErrorCode,
} from "@/types/voice";

// ---------------------------------------------------------------------------
// Backend configuration
// ---------------------------------------------------------------------------

/**
 * Local FastAPI backend URL.
 *
 * Default is http://127.0.0.1:8000 — exactly where `python run.py` puts the
 * server. If you ever need to point the frontend at a different backend,
 * set NEXT_PUBLIC_BACKEND_URL in `.env.local` (do NOT put any secrets in
 * NEXT_PUBLIC_* variables — they are bundled into the browser bundle).
 */
const BACKEND_BASE_URL = (
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  "http://127.0.0.1:8000"
).replace(/\/+$/, "");

/**
 * Build an absolute URL for the FastAPI backend.
 */
function apiUrl(path: string): string {
  return `${BACKEND_BASE_URL}${path}`;
}

// ---------------------------------------------------------------------------
// Error handling
// ---------------------------------------------------------------------------

async function asApiError(
  res: Response,
): Promise<VoiceApiError> {
  try {
    const data = (await res.json()) as VoiceApiError;

    if (
      data &&
      data.success === false &&
      data.error &&
      data.error_code
    ) {
      return data;
    }
  } catch {
    // Response was not valid JSON.
  }

  return {
    success: false,
    error: `Request failed with status ${res.status}.`,
    error_code: "network_error" as VoiceErrorCode,
  };
}

// ---------------------------------------------------------------------------
// Custom error
// ---------------------------------------------------------------------------

export class VoiceServiceError extends Error {
  code: VoiceErrorCode;

  constructor(
    code: VoiceErrorCode,
    message: string,
  ) {
    super(message);

    this.code = code;
    this.name = "VoiceServiceError";
  }
}

// ---------------------------------------------------------------------------
// Check response
// ---------------------------------------------------------------------------

async function ensureOk<T>(
  res: Response,
): Promise<T> {
  if (!res.ok) {
    const err = await asApiError(res);

    throw new VoiceServiceError(
      err.error_code,
      err.error,
    );
  }

  return (await res.json()) as T;
}

// ===========================================================================
// GET /api/health
// ===========================================================================

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(
    apiUrl("/api/health"),
    {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    },
  );

  return ensureOk<HealthResponse>(res);
}

// ===========================================================================
// GET /api/languages
// ===========================================================================

export async function fetchLanguages(): Promise<LanguagesResponse> {
  const res = await fetch(
    apiUrl("/api/languages"),
    {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    },
  );

  return ensureOk<LanguagesResponse>(res);
}

// ===========================================================================
// POST /api/stt
// Speech-to-Text
// ===========================================================================

export async function transcribeAudio(
  audioBlob: Blob,
): Promise<STTResponse> {

  console.log("========== STT DEBUG ==========");

  console.log(
    "Audio Blob size:",
    audioBlob.size,
    "bytes",
  );

  console.log(
    "Audio Blob type:",
    audioBlob.type,
  );

  // -------------------------------------------------------------------------
  // Validate audio
  // -------------------------------------------------------------------------

  if (!audioBlob) {
    throw new VoiceServiceError(
      "stt_empty_audio",
      "No audio was recorded.",
    );
  }

  if (audioBlob.size === 0) {
    throw new VoiceServiceError(
      "stt_empty_audio",
      "The recorded audio is empty.",
    );
  }

  // -------------------------------------------------------------------------
  // Determine filename
  // -------------------------------------------------------------------------

  const mimeType = (
    audioBlob.type || ""
  ).toLowerCase();

  let filename = "recording.webm";

  if (mimeType.includes("mp4")) {
    filename = "recording.mp4";
  } else if (mimeType.includes("mpeg")) {
    filename = "recording.mp3";
  } else if (mimeType.includes("wav")) {
    filename = "recording.wav";
  } else if (mimeType.includes("ogg")) {
    filename = "recording.ogg";
  } else if (mimeType.includes("webm")) {
    filename = "recording.webm";
  }

  console.log(
    "STT filename:",
    filename,
  );

  // -------------------------------------------------------------------------
  // Create multipart form
  // -------------------------------------------------------------------------

  const form = new FormData();

  form.append(
    "file",
    audioBlob,
    filename,
  );

  // -------------------------------------------------------------------------
  // Send to FastAPI
  // -------------------------------------------------------------------------

  const url = apiUrl("/api/stt");

  console.log(
    "STT request URL:",
    url,
  );

  console.log(
    "Sending audio to backend...",
  );

  const res = await fetch(
    url,
    {
      method: "POST",
      body: form,
    },
  );

  console.log(
    "STT HTTP status:",
    res.status,
  );

  // -------------------------------------------------------------------------
  // Backend error
  // -------------------------------------------------------------------------

  if (!res.ok) {
    const err = await asApiError(res);

    console.error(
      "STT backend error:",
      err,
    );

    throw new VoiceServiceError(
      err.error_code,
      err.error,
    );
  }

  // -------------------------------------------------------------------------
  // Read backend response
  // -------------------------------------------------------------------------

  const data = (
    await res.json()
  ) as STTResponse;

  console.log(
    "STT backend response:",
    data,
  );

  console.log(
    "TRANSCRIBED TEXT:",
    data.text,
  );

  console.log(
    "DETECTED LANGUAGE:",
    data.language,
  );

  console.log(
    "================================",
  );

  // -------------------------------------------------------------------------
  // Empty transcription
  // -------------------------------------------------------------------------

  if (
    !data.text ||
    !data.text.trim()
  ) {
    throw new VoiceServiceError(
      "stt_empty_result",
      "I couldn't hear anything in that recording. Try again?",
    );
  }

  return data;
}

// ===========================================================================
// POST /api/chat
// ===========================================================================

export async function chat(
  message: string,
  language: string,
  conversationHistory: ChatMessage[],
): Promise<ChatResponse> {

  const res = await fetch(
    apiUrl("/api/chat"),
    {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },

      body: JSON.stringify({
        message,
        language,
        conversation_history: conversationHistory,
      }),
    },
  );

  if (!res.ok) {
    const err = await asApiError(res);

    throw new VoiceServiceError(
      err.error_code,
      err.error,
    );
  }

  return (
    await res.json()
  ) as ChatResponse;
}

// ===========================================================================
// POST /api/tts
// ===========================================================================

export async function synthesizeSpeech(
  text: string,
  language: string,
): Promise<{
  audioUrl: string;
  mime: string;
}> {

  const res = await fetch(
    apiUrl("/api/tts"),
    {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },

      body: JSON.stringify({
        text,
        language,
      }),
    },
  );

  if (!res.ok) {
    const err = await asApiError(res);

    throw new VoiceServiceError(
      err.error_code,
      err.error,
    );
  }

  const data = (
    await res.json()
  ) as TTSResponse;

  // -------------------------------------------------------------------------
  // Convert base64 audio into Blob
  // -------------------------------------------------------------------------

  const byteChars = atob(
    data.audio_base64,
  );

  const bytes = new Uint8Array(
    byteChars.length,
  );

  for (
    let i = 0;
    i < byteChars.length;
    i++
  ) {
    bytes[i] = byteChars.charCodeAt(i);
  }

  const mime =
    data.mime_type ||
    "audio/mpeg";

  const blob = new Blob(
    [bytes],
    {
      type: mime,
    },
  );

  const audioUrl =
    URL.createObjectURL(blob);

  return {
    audioUrl,
    mime,
  };
}

// ===========================================================================
// Friendly error messages
// ===========================================================================

export function friendlyErrorMessage(
  code: string,
  fallback: string,
): string {

  const map: Record<string, string> = {

    // -----------------------------------------------------------------------
    // Speech-to-Text
    // -----------------------------------------------------------------------

    stt_no_api_key:
      "The backend has no Groq API key configured. Add GROQ_API_KEY to backend/.env.",

    stt_invalid_api_key:
      "Groq rejected the API key. Double-check it in backend/.env.",

    stt_rate_limit:
      "Groq rate limit hit. Wait a few seconds and try again.",

    stt_provider_unavailable:
      "Groq is temporarily unavailable. Try again shortly.",

    stt_provider_error:
      "Speech recognition failed. Please try recording again.",

    stt_empty_audio:
      "Empty audio. Hold the mic button while speaking.",

    stt_empty_result:
      "I couldn't hear anything in that recording. Try again.",

    stt_no_speech:
      "I couldn't detect clear speech. Please speak again.",

    stt_unsupported_format:
      "That audio format isn't supported. Try another browser.",

    stt_file_too_large:
      "The recording is too long. Keep it under 25 MB.",

    // -----------------------------------------------------------------------
    // Gemini / LLM
    // -----------------------------------------------------------------------

    llm_no_api_key:
      "The backend has no Gemini API key configured. Add GEMINI_API_KEY to backend/.env.",

    llm_invalid_api_key:
      "Gemini rejected the API key. Double-check it in backend/.env.",

    llm_rate_limit:
      "Gemini free-tier rate limit hit. Wait a moment and try again.",

    llm_model_not_found:
      "The configured Gemini model was not found. Update GEMINI_MODEL in backend/.env.",

    llm_provider_unavailable:
      "Gemini is temporarily unavailable. Try again shortly.",

    llm_provider_error:
      "The model couldn't produce a reply. Please try again.",

    llm_blocked:
      "I'm not able to answer that. Could you rephrase?",

    llm_empty_response:
      "The model returned an empty reply. Please try again.",

    // -----------------------------------------------------------------------
    // ElevenLabs / TTS
    // -----------------------------------------------------------------------

    tts_no_api_key:
      "The backend has no ElevenLabs key/voice configured.",

    tts_invalid_api_key:
      "ElevenLabs rejected the API key.",

    tts_rate_limit:
      "ElevenLabs free-tier quota exhausted.",

    tts_voice_not_found:
      "The configured ElevenLabs voice/model is invalid.",

    tts_provider_unavailable:
      "ElevenLabs is temporarily unavailable.",

    tts_provider_error:
      "Voice generation failed. Please try again.",

    tts_empty_text:
      "Nothing to synthesise.",

    tts_empty_audio:
      "The voice service returned no audio.",

    // -----------------------------------------------------------------------
    // General
    // -----------------------------------------------------------------------

    rate_limited:
      "Too many requests. Please slow down.",

    network_error:
      "Couldn't reach the backend. Is it running on port 8000?",
  };

  return (
    map[code] ??
    fallback ??
    "Something went wrong. Please try again."
  );
}