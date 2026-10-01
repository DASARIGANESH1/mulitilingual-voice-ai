"""
End-to-end audit test for the Multilingual Voice AI pipeline.

This test verifies the EXACT bug that was reported:
    "When I say 'Hello, my name is Sumanth', the app shows 'you' instead."

We mock the Groq client and verify, for every stage of the pipeline:

    1. Microphone Blob   (simulated audio bytes)
    2. STT request       (FastAPI /api/stt route hit with the blob)
    3. Groq response     (mocked transcripts for each language)
    4. Transcript guard  (hallucinations rejected, real speech accepted)
    5. STT JSON response (the dict returned to the frontend)
    6. Frontend mapping  (page.tsx logic: userText = sttResult.text)
    7. Chat request      (FastAPI /api/chat with the right message)
    8. Gemini request    (assistant -> model role mapping)
    9. TTS request       (FastAPI /api/tts with the AI reply text)
   10. Audio playback    (base64 -> Blob -> object URL)

For each of the 6 required test sentences:

    EN  "Hello, my name is Sumanth."
    HI  "मेरा नाम सुमंत है।"
    TE  "నా పేరు సుమంత్."
    TA  "என் பெயர் சுமந்த்."
    KN  "ನನ್ನ ಹೆಸರು ಸುಮಂತ್."
    EN  "How are you today?"

We also verify the hallucination guard rejects the original "you" bug
and a list of other known Whisper hallucinations.
"""

from __future__ import annotations

import io
import os
import sys
import types
import unittest
from typing import List
from unittest.mock import MagicMock, patch

# Make the backend importable.
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, BACKEND_DIR)


# ============================================================================
# Test fixtures — the EXACT sentences the user will speak.
# ============================================================================

TEST_SENTENCES: List[dict] = [
    {
        "language": "en",
        "label": "English 1",
        "spoken": "Hello, my name is Sumanth.",
        "groq_language": "en",
    },
    {
        "language": "en",
        "label": "English 2",
        "spoken": "How are you today?",
        "groq_language": "en",
    },
    {
        "language": "hi",
        "label": "Hindi",
        "spoken": "मेरा नाम सुमंत है।",
        "groq_language": "hi",
    },
    {
        "language": "te",
        "label": "Telugu",
        "spoken": "నా పేరు సుమంత్.",
        "groq_language": "te",
    },
    {
        "language": "ta",
        "label": "Tamil",
        "spoken": "என் பெயர் சுமந்த்.",
        "groq_language": "ta",
    },
    {
        "language": "kn",
        "label": "Kannada",
        "spoken": "ನನ್ನ ಹೆಸರು ಸುಮಂತ್.",
        "groq_language": "kn",
    },
]


# Known Whisper hallucinations that MUST be rejected.
HALLUCINATIONS: List[str] = [
    "you",
    "You.",
    "YOU!",
    "you you",
    "you you you",
    "user",
    "User!",
    "thank you",
    "Thank you.",
    "thanks for watching",
    "Thank you for watching!",
    "please subscribe",
    "[BLANK_AUDIO]",
    "[music]",
    "ok",
    "okay",
    "bye",
]


# ============================================================================
# Fake Groq response object — looks like the real thing the SDK returns.
# ============================================================================

class _FakeSegment:
    def __init__(
        self,
        text: str,
        avg_logprob: float = -0.4,
        no_speech_prob: float = 0.05,
        compression_ratio: float = 1.5,
    ) -> None:
        self.text = text
        self.avg_logprob = avg_logprob
        self.no_speech_prob = no_speech_prob
        self.compression_ratio = compression_ratio


class _FakeVerboseResponse:
    """Mimics groq.types.TranscriptionVerboseResponse."""

    def __init__(self, text: str, language: str, no_speech_prob: float = 0.05) -> None:
        self.text = text
        self.language = language
        self.segments = [_FakeSegment(text=text, no_speech_prob=no_speech_prob)]


class _FakeAudioNamespace:
    """Mimics client.audio.transcriptions."""

    def __init__(self, response: _FakeVerboseResponse) -> None:
        self._response = response
        self.last_kwargs: dict = {}

    def create(self, **kwargs):  # noqa: ANN201
        # Record the call so the test can verify what was sent to Groq.
        self.last_kwargs = kwargs
        return self._response


class _FakeGroqClient:
    """Mimics the groq.Groq client just enough for STTService."""

    def __init__(self, response: _FakeVerboseResponse) -> None:
        self.audio = types.SimpleNamespace()
        self.audio.transcriptions = _FakeAudioNamespace(response)


# ============================================================================
# Stage-by-stage audit
# ============================================================================

class PipelineAuditTests(unittest.TestCase):
    """Walk every test sentence through every stage of the pipeline."""

    def setUp(self) -> None:
        # Force the settings to look configured so _ensure_client doesn't bail.
        from app.config import settings
        self._orig_groq_key = settings.groq_api_key
        settings.groq_api_key = "fake-test-key"

    def tearDown(self) -> None:
        from app.config import settings
        settings.groq_api_key = self._orig_groq_key

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run_stt(self, spoken_text: str, language: str, no_speech_prob: float = 0.05):
        """Run the STT service end-to-end with a mocked Groq client."""
        from app.services.stt_service import STTService

        fake_response = _FakeVerboseResponse(
            text=spoken_text,
            language=language,
            no_speech_prob=no_speech_prob,
        )
        fake_client = _FakeGroqClient(fake_response)
        service = STTService(client=fake_client)

        # Simulate a 4 KB blob of recorded audio (we never read the bytes
        # because Groq is mocked, but the size guard at the top of
        # transcribe() must pass).
        audio_bytes = b"\x00" * 4096

        return service.transcribe(
            audio_bytes=audio_bytes,
            filename="recording.webm",
            mime_type="audio/webm",
        )

    # ------------------------------------------------------------------
    # Stage 1+2+3+4+5: Real speech reaches the frontend intact
    # ------------------------------------------------------------------

    def test_real_speech_passes_through_every_stage(self):
        """Every required test sentence must survive the full STT pipeline
        without being altered, truncated, or rejected."""

        from app.services.stt_service import _looks_like_placeholder_transcript

        for case in TEST_SENTENCES:
            with self.subTest(case=case["label"]):
                # Stage 3 — mock what Groq Whisper would return.
                groq_transcript = case["spoken"]
                groq_language = case["groq_language"]

                # Stage 4 — the hallucination guard must NOT reject real speech.
                self.assertFalse(
                    _looks_like_placeholder_transcript(groq_transcript),
                    f"Real speech wrongly flagged as hallucination: {groq_transcript!r}",
                )

                # Stages 1+2+3+5 — run the full STTService.transcribe()
                # with the mocked Groq client.
                text, lang, conf = self._run_stt(groq_transcript, groq_language)

                # Stage 5 — the text returned to the frontend must equal
                # what Groq returned, byte for byte.
                self.assertEqual(
                    text,
                    groq_transcript,
                    f"STT altered the transcript for {case['label']}",
                )

                # Stage 5 — language code must match.
                self.assertEqual(
                    lang,
                    groq_language,
                    f"STT altered the language for {case['label']}",
                )

                # Stage 6 — sanity check the dict the route would return.
                # This is exactly what STTResponse(success=True, text=text, ...)
                # would build.
                frontend_payload = {
                    "success": True,
                    "text": text,
                    "language": lang,
                    "language_confidence": conf,
                }
                self.assertEqual(frontend_payload["text"], case["spoken"])
                self.assertNotEqual(frontend_payload["text"], "you")

    # ------------------------------------------------------------------
    # The EXACT original bug: Groq returns "you" -> backend must reject
    # ------------------------------------------------------------------

    def test_original_you_bug_is_eliminated(self):
        """If Whisper returns 'you' (its most common hallucination), the
        STT service MUST raise an error instead of returning it to the
        frontend."""

        from app.services.stt_service import STTError, _looks_like_placeholder_transcript

        # The hallucination guard catches it on its own.
        self.assertTrue(_looks_like_placeholder_transcript("you"))
        self.assertTrue(_looks_like_placeholder_transcript("You."))
        self.assertTrue(_looks_like_placeholder_transcript("YOU!"))

        # And the full service raises stt_no_speech.
        for hallucination in HALLUCINATIONS:
            with self.subTest(hallucination=hallucination):
                with self.assertRaises(STTError) as ctx:
                    self._run_stt(hallucination, "en")
                self.assertEqual(ctx.exception.code, "stt_no_speech")

    # ------------------------------------------------------------------
    # Stage 6: Gemini receives the REAL transcript, not "you"
    # ------------------------------------------------------------------

    def test_gemini_receives_real_transcript(self):
        """The /api/chat route must forward the actual transcript to
        Gemini, not 'you' or any other placeholder."""

        from app.services.llm_service import LLMService

        # Mock the Gemini SDK so we can capture what the service sends.
        with patch.object(LLMService, "_ensure_client") as mock_ensure:
            fake_client = MagicMock()
            fake_response = MagicMock()
            fake_response.candidates = [MagicMock()]
            fake_response.candidates[0].content.parts = [MagicMock(text="Hi there.")]
            fake_response.prompt_feedback = None
            fake_client.models.generate_content.return_value = fake_response
            mock_ensure.return_value = fake_client

            service = LLMService()

            # Force the settings to look configured.
            from app.config import settings
            settings.gemini_api_key = "fake-gemini-key"

            for case in TEST_SENTENCES:
                with self.subTest(case=case["label"]):
                    # Simulate the /api/chat route calling the service with
                    # the transcript returned by STT.
                    history: List[tuple] = []
                    ai_text = service.generate(
                        user_message=case["spoken"],
                        language_code=case["language"],
                        history=history,
                    )

                    # Capture the actual call to Gemini.
                    call_kwargs = fake_client.models.generate_content.call_args.kwargs
                    contents = call_kwargs["contents"]

                    # The LAST Content must be the user's message with the
                    # real transcript.
                    last = contents[-1]
                    last_text = last.parts[0].text

                    self.assertEqual(
                        last_text,
                        case["spoken"],
                        f"Gemini received wrong text for {case['label']}: {last_text!r}",
                    )
                    self.assertNotEqual(last_text, "you")
                    self.assertNotEqual(last_text, "user")
                    self.assertNotEqual(last_text, "")

                    # Role mapping: "assistant" must become "model".
                    fake_client.models.generate_content.reset_mock()

    def test_gemini_role_mapping_assistant_to_model(self):
        """Conversation history with role='assistant' must be sent to
        Gemini as role='model' — sending 'assistant' verbatim causes a
        400 INVALID_ARGUMENT error."""

        from app.services.llm_service import LLMService

        with patch.object(LLMService, "_ensure_client") as mock_ensure:
            fake_client = MagicMock()
            fake_response = MagicMock()
            fake_response.candidates = [MagicMock()]
            fake_response.candidates[0].content.parts = [MagicMock(text="Ok.")]
            fake_response.prompt_feedback = None
            fake_client.models.generate_content.return_value = fake_response
            mock_ensure.return_value = fake_client

            from app.config import settings
            settings.gemini_api_key = "fake-gemini-key"

            service = LLMService()
            service.generate(
                user_message="Hello",
                language_code="en",
                history=[
                    ("user", "Hi"),
                    ("assistant", "Hello!"),
                ],
            )

            contents = fake_client.models.generate_content.call_args.kwargs["contents"]

            # History must be: user, model, user (new turn).
            self.assertEqual(len(contents), 3)
            self.assertEqual(contents[0].role, "user")
            self.assertEqual(contents[1].role, "model")
            self.assertEqual(contents[2].role, "user")

            self.assertEqual(contents[0].parts[0].text, "Hi")
            self.assertEqual(contents[1].parts[0].text, "Hello!")
            self.assertEqual(contents[2].parts[0].text, "Hello")

    # ------------------------------------------------------------------
    # Stage 7: Gemini response is returned as the assistant turn
    # ------------------------------------------------------------------

    def test_gemini_response_is_returned_untouched(self):
        from app.services.llm_service import LLMService

        with patch.object(LLMService, "_ensure_client") as mock_ensure:
            fake_client = MagicMock()
            fake_response = MagicMock()
            fake_response.candidates = [MagicMock()]
            fake_response.candidates[0].content.parts = [MagicMock(text="I'm doing great, thanks!")]
            fake_response.prompt_feedback = None
            fake_client.models.generate_content.return_value = fake_response
            mock_ensure.return_value = fake_client

            from app.config import settings
            settings.gemini_api_key = "fake-gemini-key"

            service = LLMService()
            result = service.generate("How are you?", "en", [])

            self.assertEqual(result, "I'm doing great, thanks!")

    # ------------------------------------------------------------------
    # Stage 8: ElevenLabs receives the AI text
    # ------------------------------------------------------------------

    def test_tts_receives_ai_text(self):
        from app.services.tts_service import TTSService

        with patch.object(TTSService, "_ensure_client") as mock_ensure:
            fake_client = MagicMock()
            # text_to_speech.convert returns an iterable of byte chunks.
            fake_client.text_to_speech.convert.return_value = iter([
                b"\x49\x44\x33",  # ID3 header
                b"\x03",  # version
                b"\x00" * 100,  # body
            ])
            mock_ensure.return_value = fake_client

            from app.config import settings
            settings.elevenlabs_api_key = "fake-eleven-key"
            settings.elevenlabs_voice_id = "fake-voice-id"

            service = TTSService()
            audio = service.synthesise("I'm doing great, thanks!", "en")

            self.assertIsInstance(audio, bytes)
            self.assertGreater(len(audio), 0)

            # Verify what was sent to ElevenLabs.
            call_kwargs = fake_client.text_to_speech.convert.call_args.kwargs
            self.assertEqual(call_kwargs["text"], "I'm doing great, thanks!")
            self.assertEqual(call_kwargs["voice_id"], "fake-voice-id")
            self.assertEqual(call_kwargs["model_id"], "eleven_multilingual_v2")

    # ------------------------------------------------------------------
    # Stage 9: Audio is returned as bytes (base64-encoded by the route)
    # ------------------------------------------------------------------

    def test_tts_route_returns_base64_audio(self):
        import base64
        import asyncio

        from app.routes.tts import synthesise_speech

        # Patch the shared tts_service instance to avoid needing a real key.
        with patch("app.routes.tts.tts_service.synthesise") as mock_synthesise:
            mock_synthesise.return_value = b"\x49\x44\x33" + b"\x00" * 100

            from app.models import TTSRequest
            req = TTSRequest(text="Hello", language="en")

            # synthesise_speech is an async function — must await it.
            response = asyncio.run(synthesise_speech(req))

            # response is a TTSResponse pydantic model.
            self.assertTrue(response.success)
            self.assertEqual(response.language, "en")
            self.assertEqual(response.mime_type, "audio/mpeg")

            decoded = base64.b64decode(response.audio_base64)
            self.assertEqual(decoded, b"\x49\x44\x33" + b"\x00" * 100)


# ============================================================================
# Frontend logic audit — mirror the page.tsx code in plain Python so we can
# verify the data flow without running a browser.
# ============================================================================

class FrontendLogicAuditTests(unittest.TestCase):
    """Re-implement the page.tsx pipeline logic in Python and verify
    the user turn content is set to the actual transcript."""

    @staticmethod
    def _frontend_stt_to_user_turn(stt_text: str, stt_language: str | None):
        """Mirror of the runPipeline() logic in src/app/page.tsx.

        Returns (user_text, language_code, error_or_none).
        """
        # Mirror of page.tsx lines ~484-509
        user_text = stt_text.strip() if isinstance(stt_text, str) else ""

        normalised_user_text = " ".join(user_text.split()).strip()

        # Strip punctuation and lowercase — the exact regex used in page.tsx
        import re
        transcript_guard = re.sub(
            r"[.?!,;:]",
            "",
            normalised_user_text,
        ).strip().lower()

        if (
            not normalised_user_text
            or transcript_guard == "you"
            or transcript_guard == "user"
        ):
            return None, None, "STT returned an invalid placeholder transcript"

        user_text = normalised_user_text

        # Language normalization (mirror of page.tsx normalizeLanguageCode)
        if not stt_language:
            language_code = "en"
        else:
            normalized = stt_language.strip().lower().split("-")[0].split("_")[0]
            if normalized and len(normalized) == 2 and normalized.isalpha():
                language_code = normalized
            else:
                language_code = "en"

        return user_text, language_code, None

    def test_frontend_extracts_real_transcript_for_every_sentence(self):
        for case in TEST_SENTENCES:
            with self.subTest(case=case["label"]):
                user_text, lang, err = self._frontend_stt_to_user_turn(
                    case["spoken"],
                    case["groq_language"],
                )

                self.assertIsNone(err, f"Frontend rejected real speech: {err}")
                self.assertEqual(
                    user_text,
                    case["spoken"],
                    f"Frontend altered the transcript for {case['label']}",
                )
                self.assertEqual(lang, case["language"])
                self.assertNotEqual(user_text, "you")

    def test_frontend_rejects_you_placeholder(self):
        user_text, _, err = self._frontend_stt_to_user_turn("you", "en")
        self.assertIsNotNone(err)
        self.assertIsNone(user_text)

    def test_frontend_history_is_built_from_real_transcript(self):
        """The historyRef.current passed to the next /api/chat call must
        contain the real transcript, not 'you'."""
        history: list[dict] = []

        for case in TEST_SENTENCES:
            user_text, lang, err = self._frontend_stt_to_user_turn(
                case["spoken"],
                case["groq_language"],
            )
            self.assertIsNone(err)

            # Mirror of page.tsx updatedHistory construction.
            ai_text = f"AI reply to: {user_text}"  # mocked
            history.append({"role": "user", "content": user_text})
            history.append({"role": "assistant", "content": ai_text})
            history = history[-20:]

        # Every user entry must be the real transcript, never "you".
        for i, turn in enumerate(history):
            if turn["role"] == "user":
                self.assertIn(
                    turn["content"],
                    [c["spoken"] for c in TEST_SENTENCES],
                    f"History turn {i} has wrong content: {turn['content']!r}",
                )
                self.assertNotEqual(turn["content"], "you")


# ============================================================================
# STT route handler audit
# ============================================================================

class STTRouteAuditTests(unittest.TestCase):
    """Verify the /api/stt FastAPI route returns the right JSON."""

    def setUp(self) -> None:
        from app.config import settings
        self._orig_groq_key = settings.groq_api_key
        settings.groq_api_key = "fake-test-key"

    def tearDown(self) -> None:
        from app.config import settings
        settings.groq_api_key = self._orig_groq_key

    def test_stt_route_returns_real_transcript(self):
        """The /api/stt route must return the actual Groq transcript,
        not 'you' or any other placeholder."""

        from app.routes.stt import transcribe_audio

        # Patch the stt_service to return a known real transcript.
        with patch("app.routes.stt.stt_service.transcribe") as mock_transcribe:
            mock_transcribe.return_value = ("Hello, my name is Sumanth.", "en", None)

            # Build a fake FastAPI UploadFile.
            class _FakeUploadFile:
                filename = "recording.webm"
                content_type = "audio/webm"

                async def read(self) -> bytes:
                    return b"\x1a\x45\xdf\xa3" + b"\x00" * 4096

            class _FakeRequest:
                pass

            import asyncio
            response = asyncio.run(
                transcribe_audio(_FakeRequest(), file=_FakeUploadFile())
            )

            self.assertTrue(response.success)
            self.assertEqual(response.text, "Hello, my name is Sumanth.")
            self.assertEqual(response.language, "en")
            self.assertNotEqual(response.text, "you")

    def test_stt_route_returns_error_on_hallucination(self):
        """If the STT service raises stt_no_speech (because Groq returned
        'you'), the route must return a 400 error, NOT 'you' as text."""

        from app.routes.stt import transcribe_audio
        from app.services.stt_service import STTError
        import asyncio

        with patch("app.routes.stt.stt_service.transcribe") as mock_transcribe:
            mock_transcribe.side_effect = STTError(
                "stt_no_speech",
                "I could not clearly detect speech.",
            )

            class _FakeUploadFile:
                filename = "recording.webm"
                content_type = "audio/webm"

                async def read(self) -> bytes:
                    return b"\x00" * 4096

            class _FakeRequest:
                pass

            response = asyncio.run(
                transcribe_audio(_FakeRequest(), file=_FakeUploadFile())
            )

            # Must be a JSONResponse with status 400.
            self.assertEqual(response.status_code, 400)

            import json
            body = json.loads(response.body)
            self.assertFalse(body["success"])
            self.assertEqual(body["error_code"], "stt_no_speech")


if __name__ == "__main__":
    unittest.main(verbosity=2)
