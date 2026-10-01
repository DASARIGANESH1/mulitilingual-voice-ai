"""
Utility helpers for language normalization and safe error handling.
"""

from __future__ import annotations

import re
from typing import Optional


# ============================================================================
# LANGUAGE NORMALISATION
# ============================================================================

# Common languages used by Whisper and this application.
#
# IMPORTANT:
# We keep BOTH the human-readable name and ISO-639-1 code.
#
# The previous implementation was too restrictive: if Whisper returned a
# valid language such as "id" (Indonesian), it could become None and the
# frontend would incorrectly fall back to English.
#
# This version accepts any valid-looking ISO-639-1 two-letter code as a
# fallback, while still providing friendly names for common languages.

LANGUAGE_NAME_BY_CODE: dict[str, str] = {
    # Indian languages
    "en": "English",
    "hi": "Hindi",
    "te": "Telugu",
    "ta": "Tamil",
    "kn": "Kannada",
    "ml": "Malayalam",
    "bn": "Bengali",
    "mr": "Marathi",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "ur": "Urdu",
    "or": "Odia",
    "as": "Assamese",

    # European
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "pl": "Polish",
    "uk": "Ukrainian",
    "ru": "Russian",
    "cs": "Czech",
    "sk": "Slovak",
    "ro": "Romanian",
    "hu": "Hungarian",
    "el": "Greek",
    "sv": "Swedish",
    "da": "Danish",
    "no": "Norwegian",
    "fi": "Finnish",
    "tr": "Turkish",

    # Asian
    "id": "Indonesian",
    "ms": "Malay",
    "vi": "Vietnamese",
    "th": "Thai",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "my": "Burmese",
    "tl": "Filipino",

    # Middle East / Africa
    "ar": "Arabic",
    "fa": "Persian",
    "he": "Hebrew",
    "sw": "Swahili",
    "am": "Amharic",

    # Other common Whisper languages
    "af": "Afrikaans",
    "ca": "Catalan",
    "hr": "Croatian",
    "bg": "Bulgarian",
    "sl": "Slovenian",
    "et": "Estonian",
    "lv": "Latvian",
    "lt": "Lithuanian",
    "is": "Icelandic",
    "sr": "Serbian",
}


# ============================================================================
# HUMAN NAME → CODE
# ============================================================================

_CODE_BY_NAME: dict[str, str] = {
    name.lower(): code
    for code, name in LANGUAGE_NAME_BY_CODE.items()
}


# Additional names/aliases that Whisper or clients may provide.
_EXTRA_ALIASES: dict[str, str] = {
    # English
    "english": "en",
    "eng": "en",

    # Indian
    "hindi": "hi",
    "hin": "hi",

    "telugu": "te",
    "tel": "te",

    "tamil": "ta",
    "tam": "ta",

    "kannada": "kn",
    "kan": "kn",

    "malayalam": "ml",
    "mal": "ml",

    "bengali": "bn",
    "bangla": "bn",
    "ben": "bn",

    "marathi": "mr",
    "mar": "mr",

    "gujarati": "gu",
    "guj": "gu",

    "punjabi": "pa",
    "panjabi": "pa",
    "pan": "pa",

    "urdu": "ur",
    "urd": "ur",

    "odia": "or",
    "oriya": "or",
    "ori": "or",

    "assamese": "as",
    "asm": "as",

    # European
    "spanish": "es",
    "spa": "es",

    "french": "fr",
    "fra": "fr",
    "fre": "fr",

    "german": "de",
    "deu": "de",
    "ger": "de",

    "italian": "it",
    "ita": "it",

    "portuguese": "pt",
    "por": "pt",

    "dutch": "nl",
    "nld": "nl",
    "dut": "nl",

    "polish": "pl",
    "pol": "pl",

    "ukrainian": "uk",
    "ukr": "uk",

    "russian": "ru",
    "rus": "ru",

    "turkish": "tr",
    "tur": "tr",

    # Asian
    "indonesian": "id",
    "bahasa indonesia": "id",
    "ind": "id",

    "malay": "ms",
    "msa": "ms",

    "vietnamese": "vi",
    "vie": "vi",

    "thai": "th",
    "tha": "th",

    "japanese": "ja",
    "jpn": "ja",

    "korean": "ko",
    "kor": "ko",

    "chinese": "zh",
    "zho": "zh",
    "chi": "zh",

    "filipino": "tl",
    "tagalog": "tl",
    "tgl": "tl",

    # Middle East
    "arabic": "ar",
    "ara": "ar",

    "persian": "fa",
    "farsi": "fa",
    "fas": "fa",
    "per": "fa",

    "hebrew": "he",
    "heb": "he",

    # Others
    "swahili": "sw",
    "swa": "sw",

    "afrikaans": "af",
    "afr": "af",

    "catalan": "ca",
    "cat": "ca",

    "croatian": "hr",
    "hrv": "hr",

    "greek": "el",
    "ell": "el",
    "gre": "el",

    "romanian": "ro",
    "ron": "ro",
    "rum": "ro",

    "hungarian": "hu",
    "hun": "hu",
}


_CODE_BY_NAME.update(_EXTRA_ALIASES)


# ============================================================================
# ISO-639-3 → ISO-639-1
# ============================================================================

_ISO3_TO_ISO1: dict[str, str] = {
    "eng": "en",
    "hin": "hi",
    "tel": "te",
    "tam": "ta",
    "kan": "kn",
    "mal": "ml",
    "ben": "bn",
    "mar": "mr",
    "guj": "gu",
    "pan": "pa",
    "urd": "ur",
    "ori": "or",
    "asm": "as",

    "spa": "es",
    "fra": "fr",
    "fre": "fr",
    "deu": "de",
    "ger": "de",
    "ita": "it",
    "por": "pt",
    "nld": "nl",
    "dut": "nl",
    "pol": "pl",
    "ukr": "uk",
    "rus": "ru",
    "tur": "tr",

    "ind": "id",
    "msa": "ms",
    "vie": "vi",
    "tha": "th",
    "jpn": "ja",
    "kor": "ko",
    "zho": "zh",
    "chi": "zh",
    "tgl": "tl",

    "ara": "ar",
    "fas": "fa",
    "per": "fa",
    "heb": "he",

    "swa": "sw",
    "afr": "af",
    "cat": "ca",
    "hrv": "hr",
    "ell": "el",
    "gre": "el",
    "ron": "ro",
    "rum": "ro",
    "hun": "hu",
}


def normalise_language(raw: Optional[str]) -> Optional[str]:
    """
    Convert a language value to a canonical language code.

    Examples:

        te       -> te
        TEL      -> te
        tel      -> te
        Telugu   -> te
        te-IN    -> te
        te_IN    -> te

        id       -> id
        Indonesian -> id

    IMPORTANT:
    Unknown but valid-looking two-letter language codes are preserved.

    This prevents the frontend from silently changing an unknown detected
    language to English.
    """

    if raw is None:
        return None

    value = str(raw).strip().lower()

    if not value:
        return None

    # Normalize separators.
    value = value.replace("_", "-")

    # Handle values such as:
    #
    # en-US
    # te-IN
    # id-ID
    #
    base = value.split("-")[0].strip()

    if not base:
        return None

    # Known ISO-639-1 code.
    if len(base) == 2 and base.isalpha():
        if base in LANGUAGE_NAME_BY_CODE:
            return base

        # IMPORTANT:
        # Preserve unknown ISO-looking two-letter codes instead of returning
        # None. Whisper supports many more languages than the UI dictionary.
        return base

    # ISO-639-3 code.
    if len(base) == 3 and base.isalpha():
        mapped = _ISO3_TO_ISO1.get(base)

        if mapped:
            return mapped

        mapped = _CODE_BY_NAME.get(base)

        if mapped:
            return mapped

    # Human-readable language name.
    mapped = _CODE_BY_NAME.get(value)

    if mapped:
        return mapped

    mapped = _CODE_BY_NAME.get(base)

    if mapped:
        return mapped

    return None


def language_display_name(code: Optional[str]) -> str:
    """
    Return a human-readable language name.

    Known:
        te -> Telugu
        id -> Indonesian

    Unknown valid code:
        xx -> XX

    Unknown/empty:
        Unknown
    """

    canonical = normalise_language(code)

    if not canonical:
        return "Unknown"

    known_name = LANGUAGE_NAME_BY_CODE.get(canonical)

    if known_name:
        return known_name

    # Do not return "Unknown" for a valid language code.
    return canonical.upper()


# ============================================================================
# ERROR SANITISATION
# ============================================================================

_KEY_PATTERNS = [
    re.compile(r"(sk-[A-Za-z0-9_-]{10,})"),
    re.compile(r"(gsk_[A-Za-z0-9_-]{10,})"),
    re.compile(r"(AIza[A-Za-z0-9_-]{20,})"),
    re.compile(r"([A-Fa-f0-9]{32,})"),
]


def sanitise_error(message: str, max_len: int = 300) -> str:
    """
    Redact anything that looks like an API key from an error message.
    """

    if not message:
        return ""

    cleaned = message

    for pattern in _KEY_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)

    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 3] + "..."

    return cleaned