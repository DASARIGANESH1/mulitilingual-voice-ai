import unittest

from app.services.stt_service import _looks_like_placeholder_transcript


class STTPlaceholderGuardTests(unittest.TestCase):
    """Whisper hallucinations must be detected and rejected."""

    def test_rejects_placeholder_transcripts(self):
        # Common single-word hallucinations.
        self.assertTrue(_looks_like_placeholder_transcript("you"))
        self.assertTrue(_looks_like_placeholder_transcript("You."))
        self.assertTrue(_looks_like_placeholder_transcript("YOU!"))
        self.assertTrue(_looks_like_placeholder_transcript("user"))
        self.assertTrue(_looks_like_placeholder_transcript("User!"))

        # Multi-word hallucinations.
        self.assertTrue(_looks_like_placeholder_transcript("thank you"))
        self.assertTrue(_looks_like_placeholder_transcript("Thank you."))
        self.assertTrue(_looks_like_placeholder_transcript("thanks for watching"))
        self.assertTrue(_looks_like_placeholder_transcript("Thank you for watching!"))
        self.assertTrue(_looks_like_placeholder_transcript("please subscribe"))

        # Audio tag hallucinations.
        self.assertTrue(_looks_like_placeholder_transcript("[BLANK_AUDIO]"))
        self.assertTrue(_looks_like_placeholder_transcript("[music]"))

        # Repeated hallucinations.
        self.assertTrue(_looks_like_placeholder_transcript("you you"))
        self.assertTrue(_looks_like_placeholder_transcript("you you you"))
        self.assertTrue(_looks_like_placeholder_transcript("you, you, you"))
        self.assertTrue(_looks_like_placeholder_transcript("thank you thank you"))

    def test_allows_real_speech(self):
        """Real multilingual transcriptions must NOT be rejected."""
        self.assertFalse(_looks_like_placeholder_transcript("hello there"))
        self.assertFalse(_looks_like_placeholder_transcript("Hello, my name is Sumanth."))
        self.assertFalse(_looks_like_placeholder_transcript("I am speaking in Hindi"))
        self.assertFalse(_looks_like_placeholder_transcript("मेरा नाम सुमंत है।"))
        self.assertFalse(_looks_like_placeholder_transcript("నా పేరు సుమంత్."))
        self.assertFalse(_looks_like_placeholder_transcript("என் பெயர் சுமந்த்."))
        self.assertFalse(_looks_like_placeholder_transcript("ನನ್ನ ಹೆಸರು ಸುಮಂತ್."))
        self.assertFalse(_looks_like_placeholder_transcript(""))
        self.assertFalse(_looks_like_placeholder_transcript("   "))


if __name__ == "__main__":
    unittest.main()
