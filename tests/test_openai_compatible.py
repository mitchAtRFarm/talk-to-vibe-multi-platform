import numpy as np
import pytest

from talk_to_vibe.providers.openai_compatible import OpenAICompatibleProvider


class TestOpenAICompatibleProvider:
    def test_provider_name(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:8000/v1", api_key="", model="whisper-1")
        assert p.provider_name == "OpenAI-Compatible"

    def test_model_from_config(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:8000/v1", api_key="", model="whisper-1")
        assert p.model == "whisper-1"

    def test_custom_model(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:8000/v1", api_key="", model="custom-model")
        assert p.model == "custom-model"

    def test_api_key_passed_through(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:8000/v1", api_key="testkey", model="whisper-1")
        assert p.client.api_key == "testkey"

    def test_api_key_default_fallback(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:8000/v1", api_key="", model="whisper-1")
        assert p.client.api_key == "not-needed"

    def test_api_key_default_fallback_logs_warning(self, caplog):
        with caplog.at_level("WARNING"):
            OpenAICompatibleProvider(base_url="http://localhost:8000/v1", api_key="", model="whisper-1")
        assert "No API key configured for OpenAI-Compatible provider" in caplog.text

    def test_transcribe_calls_sdk_with_prompt_and_language(self, monkeypatch):
        audio = np.zeros((16000, 1), dtype=np.int16)
        p = OpenAICompatibleProvider(
            base_url="http://localhost:8000/v1",
            api_key="testkey",
            model="whisper-1",
            language="en",
            post_process=True,
        )
        p.hints = "Expected vocabulary: TalkToVibe"

        class FakeResult:
            text = "  um, hello world  "

        class FakeTranscriptions:
            def create(self, **kwargs):
                assert kwargs["model"] == "whisper-1"
                assert kwargs["language"] == "en"
                assert kwargs["prompt"] == "Expected vocabulary: TalkToVibe"
                assert "file" in kwargs
                return FakeResult()

        class FakeAudio:
            transcriptions = FakeTranscriptions()

        class FakeClient:
            audio = FakeAudio()

        p.client = FakeClient()
        result = p.transcribe(audio)
        assert result == "Hello world"

    def test_transcribe_can_skip_post_process(self):
        audio = np.zeros((16000, 1), dtype=np.int16)
        p = OpenAICompatibleProvider(
            base_url="http://localhost:8000/v1",
            api_key="testkey",
            model="whisper-1",
            post_process=False,
        )

        class FakeResult:
            text = "  um, hello world  "

        class FakeTranscriptions:
            def create(self, **kwargs):
                return FakeResult()

        class FakeAudio:
            transcriptions = FakeTranscriptions()

        class FakeClient:
            audio = FakeAudio()

        p.client = FakeClient()
        result = p.transcribe(audio)
        assert result == "um, hello world"

    def test_no_hardcoded_defaults_in_provider(self):
        with pytest.raises(TypeError):
            OpenAICompatibleProvider(base_url="http://localhost:8000/v1")
