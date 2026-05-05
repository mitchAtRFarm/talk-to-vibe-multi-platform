from unittest.mock import patch, MagicMock

import numpy as np

from talk_to_vibe.providers.base import BaseSTTProvider


class _Fixed(BaseSTTProvider):
    provider_name = "Fixed"
    model = "fixed"

    def __init__(self, text):
        self._text = text

    def transcribe(self, audio_data):
        return self._text


class TestDefaultTranscribeStream:
    def test_yields_sentence_chunks(self):
        chunks = list(_Fixed("Hello there. How are you? I am fine!").transcribe_stream(np.zeros(1)))
        assert chunks == ["Hello there.", "How are you?", "I am fine!"]

    def test_single_sentence_yields_once(self):
        chunks = list(_Fixed("just one sentence here").transcribe_stream(np.zeros(1)))
        assert chunks == ["just one sentence here"]

    def test_empty_text_yields_nothing(self):
        chunks = list(_Fixed("").transcribe_stream(np.zeros(1)))
        assert chunks == []

    def test_whitespace_only_yields_nothing(self):
        chunks = list(_Fixed("   \n  ").transcribe_stream(np.zeros(1)))
        assert chunks == []


class TestLocalWhisperStreamingShape:
    """Confirm LocalWhisperProvider.transcribe_stream yields per-segment text
    in order and skips blank segments. We mock the underlying WhisperModel."""

    def test_yields_each_non_empty_segment_in_order(self):
        # Defer import so missing optional deps don't break the suite.
        from talk_to_vibe.providers.local_whisper import LocalWhisperProvider

        seg1 = MagicMock(text=" Hello world")
        seg2 = MagicMock(text="")
        seg3 = MagicMock(text=" how are you")

        fake_model = MagicMock()
        fake_model.transcribe.return_value = (iter([seg1, seg2, seg3]), MagicMock())

        provider = LocalWhisperProvider.__new__(LocalWhisperProvider)
        provider._whisper = fake_model
        provider.language = "en"
        provider.beam_size = 5
        provider.vad_filter = True
        provider.initial_prompt = ""
        provider.post_process = False

        audio = np.zeros(16000, dtype=np.int16)
        chunks = list(provider.transcribe_stream(audio))
        assert chunks == ["Hello world", "how are you"]

    def test_transcribe_returns_joined_stream(self):
        from talk_to_vibe.providers.local_whisper import LocalWhisperProvider

        seg1 = MagicMock(text=" Hello world")
        seg2 = MagicMock(text=" how are you")

        fake_model = MagicMock()
        fake_model.transcribe.return_value = (iter([seg1, seg2]), MagicMock())

        provider = LocalWhisperProvider.__new__(LocalWhisperProvider)
        provider._whisper = fake_model
        provider.language = "en"
        provider.beam_size = 5
        provider.vad_filter = True
        provider.initial_prompt = ""
        provider.post_process = False

        audio = np.zeros(16000, dtype=np.int16)
        assert provider.transcribe(audio) == "Hello world how are you"

    def test_empty_audio_yields_nothing(self):
        from talk_to_vibe.providers.local_whisper import LocalWhisperProvider

        fake_model = MagicMock()
        provider = LocalWhisperProvider.__new__(LocalWhisperProvider)
        provider._whisper = fake_model
        provider.language = "en"
        provider.beam_size = 5
        provider.vad_filter = True
        provider.initial_prompt = ""
        provider.post_process = False

        chunks = list(provider.transcribe_stream(np.array([], dtype=np.int16)))
        assert chunks == []
        fake_model.transcribe.assert_not_called()
