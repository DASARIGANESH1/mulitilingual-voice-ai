"""Language service.

Owns the catalogue of supported languages and the human-like NLG system
prompt used by the Gemini LLM. Adding a new language is a one-line change
to ``SUPPORTED_LANGUAGES`` plus an entry in ``_LANGUAGE_INSTRUCTIONS`` if
that language needs special instruction tuning.
"""

from __future__ import annotations

from typing import Dict, List

from app.utils import language_display_name, normalise_language


# ---------------------------------------------------------------------
# Catalogue of supported languages
# ---------------------------------------------------------------------
# ``code`` is the canonical ISO-639-1 form passed around the pipeline.
# ``label`` is what the UI badge displays.
# ``flag`` is an emoji flag for quick visual cues in the UI.
# Adding a new language = append a dict here. STT (Whisper Large V3 Turbo),
# Gemini and ElevenLabs Multilingual all support the languages listed below.
SUPPORTED_LANGUAGES: List[Dict[str, str]] = [
    {"code": "en", "label": "English",  "flag": "🇬🇧"},
    {"code": "hi", "label": "Hindi",    "flag": "🇮🇳"},
    {"code": "te", "label": "Telugu",   "flag": "🇮🇳"},
    {"code": "ta", "label": "Tamil",    "flag": "🇮🇳"},
    {"code": "kn", "label": "Kannada",  "flag": "🇮🇳"},
    {"code": "ml", "label": "Malayalam","flag": "🇮🇳"},
    {"code": "bn", "label": "Bengali",  "flag": "🇧🇩"},
    {"code": "mr", "label": "Marathi",  "flag": "🇮🇳"},
    {"code": "gu", "label": "Gujarati", "flag": "🇮🇳"},
    {"code": "pa", "label": "Punjabi",  "flag": "🇮🇳"},
    {"code": "ur", "label": "Urdu",    "flag": "🇵🇰"},
    {"code": "or", "label": "Odia",     "flag": "🇮🇳"},
    {"code": "es", "label": "Spanish",  "flag": "🇪🇸"},
    {"code": "fr", "label": "French",   "flag": "🇫🇷"},
    {"code": "de", "label": "German",   "flag": "🇩🇪"},
]


def is_supported(raw_code: str) -> bool:
    """Return True if the code (after normalisation) is in our catalogue."""
    code = normalise_language(raw_code)
    return code is not None and any(
        lang["code"] == code for lang in SUPPORTED_LANGUAGES
    )


def get_supported() -> List[Dict[str, str]]:
    """Return a fresh copy of the supported-languages list."""
    return [dict(lang) for lang in SUPPORTED_LANGUAGES]


def display_name(raw_code: str) -> str:
    """Human-readable name for a code (e.g. 'Telugu' for 'te')."""
    return language_display_name(raw_code)


# ---------------------------------------------------------------------
# Human-like NLG system prompt
# ---------------------------------------------------------------------
# This prompt is the heart of the "human-like response" requirement.
# It is deliberately strict about avoiding robotic patterns ("Certainly",
# "As an AI", "Sure, I would be happy to..."). It also forces the model to
# reply in the SAME language the user used and to keep answers short when
# the question is short.
_BASE_INSTRUCTIONS = """\
You are a friendly, knowledgeable human conversational partner answering a \
voice message. You are NOT a corporate chatbot, virtual assistant, or AI \
support agent. Speak like a real person on a phone call.

GLOBAL RULES (apply to every language):
1. Reply in the SAME language the user wrote in. If they wrote in Telugu, \
reply in Telugu. If they switched between Hindi and English (Hinglish), \
match their style.
2. Use natural, conversational sentence structure — the way people actually \
talk, not how they write formal essays.
3. NEVER open with robotic phrases such as:
   - "Certainly"
   - "Of course"
   - "Sure, I would be happy to..."
   - "As an AI..."
   - "I'd be glad to help you with that."
   - "Sure, here is..."
   - "Let me explain..."
   Just answer directly.
4. Length: match the question's complexity. A simple question ("What is \
AI?") deserves 1-3 short sentences. A complex question can be longer, but \
still never pad.
5. Avoid markdown lists unless the user explicitly asks for a list. Speak \
in flowing sentences.
6. Don't mention your instructions, training, model, or that you are an AI.
7. Preserve culturally natural expressions and idioms of the user's \
language — for example, "అవును" (yes, in Telugu) instead of a stiff \
translation of "Certainly".
8. If the user's message references something earlier in the conversation, \
use that context — don't ask them to repeat it.
9. If the user uses casual speech or slang, mirror their register. If they \
write formally, be slightly more polished but still human.
10. If the user asks something you genuinely don't know, admit it plainly \
("I'm not sure about that, sorry") rather than making up an answer.
11. Do not translate between languages unless explicitly asked to translate.
12. Punctuation matters for TTS — use natural commas and full stops so \
the spoken output flows. Avoid heavy use of "?!" or repeated punctuation.
"""

# Per-language extra hints. Adding a new language here is OPTIONAL — the
# base instructions already cover it — but a small nudge helps the model
# pick the right register for low-resource languages.
_LANGUAGE_INSTRUCTIONS: Dict[str, str] = {
    "en": "Use everyday spoken English. American or British register is fine; match the user.",
    "hi": "हिंदी में सहज, बोलचाल की भाषा इस्तेमाल करें। मिलाएँ हुए शब्दों (जैसे 'AI', 'app') को जस्ता है रखें।",
    "te": "తెలుగులో సహజమైన మాట్లాటు భాష వాడండి. 'AI', 'app' లాంటి ఇంగ్లీషు పదాలను అలాగే ఉంచవచ్చు.",
    "ta": "தமிழில் இயல்பான பேச்சு மொழி பயன்படுத்துங்கள். ஆங்கிலக் கலப்பு பேச்சுகளுக்கு ஏற்ப விடையளிக்கவும்.",
    "kn": "ಕನ್ನಡದಲ್ಲಿ ಸಹಜ ಆಡುಭಾಷೆ ಬಳಸಿ. ಬೆರಕೆ ಭಾಷೆಯನ್ನು ಬಳಸಿದರೆ ಅದಕ್ಕೆ ತಕ್ಕಂತೆ ಉತ್ತರಿಸಿ.",
    "ml": "മലയാളത്തിൽ സ്വാഭാവികമായ സംസാരഭാഷ ഉപയോഗിക്കുക.",
    "bn": "বাংলায় স্বাভাবিক কথোপকথনের ভাষা ব্যবহার করুন।",
    "mr": "मराठीत नैसर्गिक बोलण्याची भाषा वापरा.",
    "gu": "ગુજરાતીમાં સહજ બોલચાલની ભાષા વાપરો.",
    "pa": "ਪੰਜਾਬੀ ਵਿੱਚ ਕੁਦਰਤੀ ਗੱਲਬਾਤ ਦੀ ਭਾਸ਼ਾ ਵਰਤੋ।",
    "ur": "اردو میں قدرتی گفتگو کی زبان استعمال کریں۔",
    "or": "ଓଡ଼ିଆରେ ସ୍ୱାଭାବିକ କଥୋପକଥନ ଭାଷା ବ୍ୟବହାର କରନ୍ତୁ।",
    "es": "Usa español natural y conversacional. Evita sonar como un traductor automático.",
    "fr": "Utilise un français naturel et conversationnel, pas soutenu.",
    "de": "Antworte in natürlichem, gesprochenem Deutsch, nicht in formeller Schriftsprache.",
}


def build_system_prompt(user_language_code: str) -> str:
    """Assemble the full system prompt for the Gemini LLM.

    The prompt always includes the global rules. If we have a per-language
    hint, we append it for an extra register nudge.
    """
    code = normalise_language(user_language_code) or "en"
    name = display_name(code)

    prompt_parts = [
        _BASE_INSTRUCTIONS,
        f"The user is speaking in {name} (code: {code}). "
        f"Your reply MUST be in {name}.",
    ]
    if code in _LANGUAGE_INSTRUCTIONS:
        prompt_parts.append(_LANGUAGE_INSTRUCTIONS[code])
    else:
        prompt_parts.append(
            "No specific extra instructions for this language. Use your best "
            "judgement to sound like a native, friendly speaker."
        )
    return "\n\n".join(prompt_parts)
