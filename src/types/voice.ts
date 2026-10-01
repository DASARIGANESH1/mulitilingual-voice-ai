/**
 * Shared types for the multilingual voice AI frontend.
 *
 * These mirror the backend Pydantic schemas in `backend/app/models/__init__.py`.
 * Keep them in sync when you change an API contract.
 */

export type LanguageCode = string; // ISO-639-1 ("en", "hi", "te", ...)

export interface LanguageInfo {
  code: LanguageCode;
  label: string; // "Telugu"
  flag: string; // emoji flag
}

/** A single previous turn in the conversation history sent to /api/chat. */
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

/** Visual representation of a conversation message in the UI. */
export interface ConversationTurn extends ChatMessage {
  id: string;
  language?: LanguageCode;
  audioUrl?: string; // object URL for AI replies (TTS audio)
  pending?: boolean; // true while we are waiting on a backend stage
  error?: boolean;
}

/** Response shape from GET /api/health. */
export interface HealthResponse {
  status: "ok";
  services: {
    stt: ProviderInfo;
    llm: ProviderInfo;
    tts: ProviderInfo;
  };
}

export interface ProviderInfo {
  provider: string;
  model: string;
  configured: boolean;
  voice_id_set?: boolean;
}

/** Response shape from GET /api/languages. */
export interface LanguagesResponse {
  success: true;
  languages: LanguageInfo[];
}

/** Response shape from POST /api/stt. */
export interface STTResponse {
  success: true;
  text: string;
  language?: LanguageCode | null;
  language_confidence?: number | null;
}

/** Response shape from POST /api/chat. */
export interface ChatResponse {
  success: true;
  response: string;
  language: LanguageCode;
}

/** Response shape from POST /api/tts. */
export interface TTSResponse {
  success: true;
  language: LanguageCode;
  audio_base64: string;
  mime_type: string;
}

/** Standard error envelope returned by every failing endpoint. */
export interface VoiceApiError {
  success: false;
  error: string;
  error_code: VoiceErrorCode;
}

export type VoiceErrorCode =
  | "stt_no_api_key"
  | "stt_invalid_api_key"
  | "stt_rate_limit"
  | "stt_provider_unavailable"
  | "stt_provider_error"
  | "stt_empty_audio"
  | "stt_empty_result"
  | "stt_unsupported_format"
  | "stt_file_too_large"
  | "stt_read_failed"
  | "stt_internal_error"
  | "llm_no_api_key"
  | "llm_invalid_api_key"
  | "llm_rate_limit"
  | "llm_model_not_found"
  | "llm_provider_unavailable"
  | "llm_provider_error"
  | "llm_blocked"
  | "llm_empty_response"
  | "llm_internal_error"
  | "tts_no_api_key"
  | "tts_invalid_api_key"
  | "tts_rate_limit"
  | "tts_voice_not_found"
  | "tts_provider_unavailable"
  | "tts_provider_error"
  | "tts_empty_text"
  | "tts_empty_audio"
  | "tts_internal_error"
  | "rate_limited"
  | "network_error";

/** Stages of the end-to-end pipeline. */
export type PipelineStage =
  | "idle"
  | "recording"
  | "transcribing"
  | "thinking"
  | "generating"
  | "speaking"
  | "done"
  | "error";
