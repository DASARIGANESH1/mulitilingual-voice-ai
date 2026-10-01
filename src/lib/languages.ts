/**
 * Language metadata for the UI.
 *
 * The authoritative list is the backend (backend/app/services/language_service.py).
 * We mirror a minimal copy here so the UI can render badges / pickers
 * without an extra round-trip on first paint.
 */

import type { LanguageCode, LanguageInfo } from "@/types/voice";

export const SUPPORTED_LANGUAGES: LanguageInfo[] = [
  { code: "en", label: "English",   flag: "🇬🇧" },
  { code: "hi", label: "Hindi",     flag: "🇮🇳" },
  { code: "te", label: "Telugu",    flag: "🇮🇳" },
  { code: "ta", label: "Tamil",     flag: "🇮🇳" },
  { code: "kn", label: "Kannada",   flag: "🇮🇳" },
  { code: "ml", label: "Malayalam", flag: "🇮🇳" },
  { code: "bn", label: "Bengali",   flag: "🇧🇩" },
  { code: "mr", label: "Marathi",   flag: "🇮🇳" },
  { code: "gu", label: "Gujarati",  flag: "🇮🇳" },
  { code: "pa", label: "Punjabi",   flag: "🇮🇳" },
  { code: "ur", label: "Urdu",     flag: "🇵🇰" },
  { code: "or", label: "Odia",      flag: "🇮🇳" },
  { code: "es", label: "Spanish",   flag: "🇪🇸" },
  { code: "fr", label: "French",    flag: "🇫🇷" },
  { code: "de", label: "German",    flag: "🇩🇪" },
];

const LANG_BY_CODE: Record<LanguageCode, LanguageInfo> = SUPPORTED_LANGUAGES.reduce(
  (acc, lang) => {
    acc[lang.code] = lang;
    return acc;
  },
  {} as Record<LanguageCode, LanguageInfo>,
);

/** Return a human-readable name like "Telugu" for a code; falls back to the raw code. */
export function languageLabel(code: LanguageCode | null | undefined): string {
  if (!code) return "Unknown";
  return LANG_BY_CODE[code]?.label ?? code.toUpperCase();
}

/** Return the emoji flag for a code; falls back to 🌐. */
export function languageFlag(code: LanguageCode | null | undefined): string {
  if (!code) return "🌐";
  return LANG_BY_CODE[code]?.flag ?? "🌐";
}
