import sys
import types

import numpy as np

from talk_to_vibe.providers.local_whisper import LocalWhisperProvider


class TestLocalWhisperProvider:
    def test_transcribe_joins_segments_with_spaces(self, monkeypatch):
        class FakeWhisperModel:
            def __init__(self, model_size, **kwargs):
                self.model_size = model_size
                self.kwargs = kwargs

            def transcribe(self, samples, language, task, beam_size, vad_filter, **kwargs):
                segments = [
                    types.SimpleNamespace(text="Hello"),
                    types.SimpleNamespace(text="world"),
                    types.SimpleNamespace(text=" from Whisper "),
                    types.SimpleNamespace(text=""),
                ]
                return segments, object()

        monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeWhisperModel))

        provider = LocalWhisperProvider(model_size="small", device="cpu", compute_type="int8")
        audio = np.zeros((16000, 1), dtype=np.int16)

        assert provider.transcribe(audio) == "Hello world from Whisper"

    def test_transcribe_dedupes_repeated_tail_across_segments(self, monkeypatch):
        class FakeWhisperModel:
            def __init__(self, model_size, **kwargs):
                pass

            def transcribe(self, samples, language, task, beam_size, vad_filter, **kwargs):
                segments = [
                    types.SimpleNamespace(text="That should work."),
                    types.SimpleNamespace(text="Thank you."),
                    types.SimpleNamespace(text="Thank you."),
                    types.SimpleNamespace(text="Thank you."),
                ]
                return segments, object()

        monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeWhisperModel))

        provider = LocalWhisperProvider(model_size="small", device="cpu", compute_type="int8")
        audio = np.zeros((16000, 1), dtype=np.int16)

        assert provider.transcribe(audio) == "That should work. Thank you."
