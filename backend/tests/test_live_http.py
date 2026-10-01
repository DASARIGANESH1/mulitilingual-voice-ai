"""
Live end-to-end integration test using FastAPI's TestClient.

This test exercises the actual HTTP layer (CORS, routing, multipart upload,
JSON parsing, error envelopes) for every endpoint, with the AI provider
clients mocked so we don't need real API keys.

It also verifies the exact original bug — saying "Hello, my name is Sumanth"
must produce a user bubble that contains that exact sentence, never "you".
"""

from __future__ import annotations

import io
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, BACKEND_DIR)


class LiveHTTPIntegrationTests(unittest.TestCase):
    """Hit each endpoint over FastAPI's in-process test client."""

    def setUp(self) -> None:
        # Force the settings to look fully configured.
        from app.config import settings
        self._settings = settings
        self._orig = {
            "groq_api_key": settings.groq_api_key,
            "gemini_api_key": settings.gemini_api_key,
            "elevenlabs_api_key": settings.elevenlabs_api_key,
            "elevenlabs_voice_id": settings.elevenlabs_voice_id,
        }
        settings.groq_api_key = "fake-groq-key"
        settings.gemini_api_key = "fake-gemini-key"
        settings.elevenlabs_api_key = "fake-eleven-key"
        settings.elevenlabs_voice_id = "fake-voice-id"

        from fastapi.testclient import TestClient
        from app.main import app
        self._client = TestClient(app)

    def tearDown(self) -> None:
        for k, v in self._orig.items():
            setattr(self._settings, k, v)

    # ------------------------------------------------------------------
    # GET /api/health
    # ------------------------------------------------------------------

    def test_health_endpoint(self):
        res = self._client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "ok")
        self.assertTrue(body["services"]["stt"]["configured"])
        self.assertTrue(body["services"]["llm"]["configured"])
        self.assertTrue(body["services"]["tts"]["configured"])

    # ------------------------------------------------------------------
    # GET /api/languages
    # ------------------------------------------------------------------

    def test_languages_endpoint_returns_all_required_codes(self):
        res = self._client.get("/api/languages")
        self.assertEqual(res.status_code, 200)
        codes = {lang["code"] for lang in res.json()["languages"]}
        for required in {"en", "hi", "te", "ta", "kn"}:
            self.assertIn(required, codes)

    # ------------------------------------------------------------------
    # POST /api/stt — REAL speech must reach the frontend intact
    # ------------------------------------------------------------------

    def _make_audio_upload(self, spoken_text: str):
        """Build a multipart upload that looks like a browser recording."""
        # Minimal valid WebM header bytes — Whisper/Groq is mocked so the
        # actual bytes don't matter, only the file metadata does.
        audio_bytes = b"\x1a\x45\xdf\xa3" + b"\x00" * 4096
        return audio_bytes, "recording.webm", "audio/webm"

    def test_stt_returns_real_transcript_for_every_sentence(self):
        """For every required test sentence, /api/stt must return the
        actual spoken words as `text`, never 'you'."""

        test_cases = [
            ("Hello, my name is Sumanth.", "en"),
            ("How are you today?", "en"),
            ("मेरा नाम सुमंत है।", "hi"),
            ("నా పేరు సుమంత్.", "te"),
            ("என் பெயர் சுமந்த்.", "ta"),
            ("ನನ್ನ ಹೆಸರು ಸುಮಂತ್.", "kn"),
        ]

        for spoken, language in test_cases:
            with self.subTest(spoken=spoken, language=language):
                # Mock the Groq client to return this transcript.
                fake_response = MagicMock()
                fake_response.text = spoken
                fake_response.language = language
                fake_response.segments = []

                with patch(
                    "app.services.stt_service.stt_service._client"
                ) as mock_client:
                    mock_client.audio.transcriptions.create.return_value = fake_response

                    audio_bytes, filename, mime = self._make_audio_upload(spoken)
                    res = self._client.post(
                        "/api/stt",
                        files={"file": (filename, audio_bytes, mime)},
                    )

                self.assertEqual(
                    res.status_code, 200,
                    f"STT returned {res.status_code} for {spoken!r}: {res.text}",
                )
                body = res.json()
                self.assertTrue(body["success"])
                self.assertEqual(body["text"], spoken)
                self.assertEqual(body["language"], language)
                self.assertNotEqual(body["text"], "you")

    # ------------------------------------------------------------------
    # POST /api/stt — hallucinations must produce a 400 error, NOT "you"
    # ------------------------------------------------------------------

    def test_stt_rejects_hallucinations(self):
        """When Groq returns a known hallucination, /api/stt must
        respond with a 400 error code, NOT return the hallucination
        as `text`."""

        hallucinations = [
            "you",
            "You.",
            "you you you",
            "thank you",
            "thanks for watching",
            "[BLANK_AUDIO]",
        ]

        for h in hallucinations:
            with self.subTest(hallucination=h):
                fake_response = MagicMock()
                fake_response.text = h
                fake_response.language = "en"
                fake_response.segments = []

                with patch(
                    "app.services.stt_service.stt_service._client"
                ) as mock_client:
                    mock_client.audio.transcriptions.create.return_value = fake_response

                    audio_bytes, filename, mime = self._make_audio_upload(h)
                    res = self._client.post(
                        "/api/stt",
                        files={"file": (filename, audio_bytes, mime)},
                    )

                self.assertEqual(res.status_code, 400)
                body = res.json()
                self.assertFalse(body["success"])
                self.assertIn(body["error_code"], {"stt_no_speech", "stt_empty_result"})

    # ------------------------------------------------------------------
    # POST /api/chat — Gemini receives the real transcript
    # ------------------------------------------------------------------

    def test_chat_returns_response_in_user_language(self):
        """For each test sentence, /api/chat must call Gemini with the
        actual transcript as the user message (not 'you') and return
        a non-empty reply."""

        test_cases = [
            ("Hello, my name is Sumanth.", "en", "Nice to meet you, Sumanth!"),
            ("How are you today?", "en", "I'm doing great, thanks for asking!"),
            ("मेरा नाम सुमंत है।", "hi", "नमस्ते सुमंत!"),
            ("నా పేరు సుమంత్.", "te", "నమస్తే సుమంత్!"),
            ("என் பெயர் சுமந்த்.", "ta", "வணக்கம் சுமந்த்!"),
            ("ನನ್ನ ಹೆಸರು ಸುಮಂತ್.", "kn", "ನಮಸ್ಕಾರ ಸುಮಂತ್!"),
        ]

        for user_msg, language, fake_ai_reply in test_cases:
            with self.subTest(language=language, msg=user_msg):
                # Mock the Gemini client.
                fake_genai_response = MagicMock()
                fake_candidate = MagicMock()
                fake_part = MagicMock()
                fake_part.text = fake_ai_reply
                fake_candidate.content.parts = [fake_part]
                fake_genai_response.candidates = [fake_candidate]
                fake_genai_response.prompt_feedback = None

                with patch(
                    "app.services.llm_service.llm_service._client"
                ) as mock_client:
                    mock_client.models.generate_content.return_value = fake_genai_response

                    res = self._client.post(
                        "/api/chat",
                        json={
                            "message": user_msg,
                            "language": language,
                            "conversation_history": [],
                        },
                    )

                self.assertEqual(res.status_code, 200, res.text)
                body = res.json()
                self.assertTrue(body["success"])
                self.assertEqual(body["response"], fake_ai_reply)
                self.assertEqual(body["language"], language)

                # Verify the message Gemini actually received.
                call_kwargs = mock_client.models.generate_content.call_args.kwargs
                last_content = call_kwargs["contents"][-1]
                self.assertEqual(last_content.parts[0].text, user_msg)
                self.assertNotEqual(last_content.parts[0].text, "you")

    # ------------------------------------------------------------------
    # POST /api/chat — multi-turn: assistant role mapped to model
    # ------------------------------------------------------------------

    def test_chat_multi_turn_role_mapping(self):
        """In multi-turn conversations, the /api/chat route must send
        'model' as the role for previous AI turns, never 'assistant'."""

        fake_genai_response = MagicMock()
        fake_candidate = MagicMock()
        fake_part = MagicMock()
        fake_part.text = "Sure!"
        fake_candidate.content.parts = [fake_part]
        fake_genai_response.candidates = [fake_candidate]
        fake_genai_response.prompt_feedback = None

        with patch(
            "app.services.llm_service.llm_service._client"
        ) as mock_client:
            mock_client.models.generate_content.return_value = fake_genai_response

            res = self._client.post(
                "/api/chat",
                json={
                    "message": "What's my name?",
                    "language": "en",
                    "conversation_history": [
                        {"role": "user", "content": "My name is Sumanth."},
                        {"role": "assistant", "content": "Nice to meet you!"},
                    ],
                },
            )

        self.assertEqual(res.status_code, 200, res.text)
        contents = mock_client.models.generate_content.call_args.kwargs["contents"]
        # user, model, user (3 turns total)
        self.assertEqual([c.role for c in contents], ["user", "model", "user"])
        self.assertEqual(contents[1].parts[0].text, "Nice to meet you!")

    # ------------------------------------------------------------------
    # POST /api/tts — audio is returned as base64
    # ------------------------------------------------------------------

    def test_tts_returns_audio(self):
        fake_audio = b"\x49\x44\x33" + b"\x00" * 100  # ID3 + body

        with patch(
            "app.services.tts_service.tts_service._client"
        ) as mock_client:
            mock_client.text_to_speech.convert.return_value = iter([fake_audio])

            res = self._client.post(
                "/api/tts",
                json={"text": "Hello world", "language": "en"},
            )

        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["mime_type"], "audio/mpeg")
        import base64
        decoded = base64.b64decode(body["audio_base64"])
        self.assertEqual(decoded, fake_audio)

    # ------------------------------------------------------------------
    # CORS headers
    # ------------------------------------------------------------------

    def test_cors_allows_localhost_3000(self):
        res = self._client.options(
            "/api/stt",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertIn(res.status_code, {200, 204})
        self.assertEqual(
            res.headers.get("access-control-allow-origin"),
            "http://localhost:3000",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
