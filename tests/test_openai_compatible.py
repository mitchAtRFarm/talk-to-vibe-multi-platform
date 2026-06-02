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

    def test_default_field_values(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:8000/v1", api_key="testkey", model="whisper-1")
        assert p.language == ""
        assert p.post_process is True
        assert p.temperature == 0
        assert p.verify_ssl is True
        assert len(p.hints) > 0  # bundled hints loaded when hints_file is empty

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

    def test_default_temperature_passed_to_sdk(self, monkeypatch):
        audio = np.zeros((16000, 1), dtype=np.int16)
        p = OpenAICompatibleProvider(
            base_url="http://localhost:8000/v1",
            api_key="testkey",
            model="whisper-1",
        )

        captured = {}

        class FakeResult:
            text = "hello world"

        class FakeTranscriptions:
            def create(self, **kwargs):
                captured["kwargs"] = kwargs
                return FakeResult()

        class FakeAudio:
            transcriptions = FakeTranscriptions()

        class FakeClient:
            audio = FakeAudio()

        p.client = FakeClient()
        p.transcribe(audio)
        assert captured["kwargs"]["temperature"] == 0

    def test_temperature_passed_to_sdk(self, monkeypatch):
        audio = np.zeros((16000, 1), dtype=np.int16)
        p = OpenAICompatibleProvider(
            base_url="http://localhost:8000/v1",
            api_key="testkey",
            model="whisper-1",
            temperature=0.5,
        )

        captured = {}

        class FakeResult:
            text = "hello world"

        class FakeTranscriptions:
            def create(self, **kwargs):
                captured["kwargs"] = kwargs
                return FakeResult()

        class FakeAudio:
            transcriptions = FakeTranscriptions()

        class FakeClient:
            audio = FakeAudio()

        p.client = FakeClient()
        p.transcribe(audio)
        assert captured["kwargs"]["temperature"] == 0.5

    def test_temperature_zero_explicitly_sent(self, monkeypatch):
        audio = np.zeros((16000, 1), dtype=np.int16)
        p = OpenAICompatibleProvider(
            base_url="http://localhost:8000/v1",
            api_key="testkey",
            model="whisper-1",
            temperature=0,
        )

        captured = {}

        class FakeResult:
            text = "hello world"

        class FakeTranscriptions:
            def create(self, **kwargs):
                captured["kwargs"] = kwargs
                return FakeResult()

        class FakeAudio:
            transcriptions = FakeTranscriptions()

        class FakeClient:
            audio = FakeAudio()

        p.client = FakeClient()
        p.transcribe(audio)
        assert captured["kwargs"]["temperature"] == 0

    def test_empty_language_omitted_from_sdk(self, monkeypatch):
        audio = np.zeros((16000, 1), dtype=np.int16)
        p = OpenAICompatibleProvider(
            base_url="http://localhost:8000/v1",
            api_key="testkey",
            model="whisper-1",
            language="",
        )

        captured = {}

        class FakeResult:
            text = "hello world"

        class FakeTranscriptions:
            def create(self, **kwargs):
                captured["kwargs"] = kwargs
                return FakeResult()

        class FakeAudio:
            transcriptions = FakeTranscriptions()

        class FakeClient:
            audio = FakeAudio()

        p.client = FakeClient()
        p.transcribe(audio)
        assert "language" not in captured["kwargs"]

    def test_hints_loaded_from_file_and_passed(self, monkeypatch, tmp_path):
        custom_hints = tmp_path / "custom_hints.md"
        custom_hints.write_text("Expected vocabulary: TalkToVibe\n")

        audio = np.zeros((16000, 1), dtype=np.int16)
        p = OpenAICompatibleProvider(
            base_url="http://localhost:8000/v1",
            api_key="testkey",
            model="whisper-1",
            hints_file=str(custom_hints),
        )

        captured = {}

        class FakeResult:
            text = "hello world"

        class FakeTranscriptions:
            def create(self, **kwargs):
                captured["kwargs"] = kwargs
                return FakeResult()

        class FakeAudio:
            transcriptions = FakeTranscriptions()

        class FakeClient:
            audio = FakeAudio()

        p.client = FakeClient()
        p.transcribe(audio)
        assert captured["kwargs"]["prompt"] == "Expected vocabulary: TalkToVibe"

    def test_missing_hints_file_falls_back_to_empty(self, monkeypatch, tmp_path):
        missing_file = tmp_path / "does_not_exist.md"

        audio = np.zeros((16000, 1), dtype=np.int16)
        p = OpenAICompatibleProvider(
            base_url="http://localhost:8000/v1",
            api_key="testkey",
            model="whisper-1",
            hints_file=str(missing_file),
        )

        captured = {}

        class FakeResult:
            text = "hello world"

        class FakeTranscriptions:
            def create(self, **kwargs):
                captured["kwargs"] = kwargs
                return FakeResult()

        class FakeAudio:
            transcriptions = FakeTranscriptions()

        class FakeClient:
            audio = FakeAudio()

        p.client = FakeClient()
        p.transcribe(audio)
        assert "prompt" not in captured["kwargs"]

    def test_post_process_applies_clean_transcript(self, monkeypatch):
        audio = np.zeros((16000, 1), dtype=np.int16)
        p = OpenAICompatibleProvider(
            base_url="http://localhost:8000/v1",
            api_key="testkey",
            model="whisper-1",
            post_process=True,
        )

        class FakeResult:
            text = "Um, hello world"

        class FakeTranscriptions:
            def create(self, **kwargs):
                return FakeResult()

        class FakeAudio:
            transcriptions = FakeTranscriptions()

        class FakeClient:
            audio = FakeAudio()

        p.client = FakeClient()
        result = p.transcribe(audio)
        assert result == "Hello world"

    def test_post_process_disabled_returns_raw(self, monkeypatch):
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

    def test_all_new_fields_roundtrip_through_factory(self, tmp_path):
        from talk_to_vibe.config.models import AppConfig, ProviderConfig, OpenAICompatibleConfig
        from talk_to_vibe.providers.factory import create_provider

        custom_hints = tmp_path / "hints.md"
        custom_hints.write_text("Custom vocabulary: TestApp\n")

        config = AppConfig(
            provider="openai_compatible",
            providers=ProviderConfig(
                openai_compatible=OpenAICompatibleConfig(
                    base_url="http://localhost:8000/v1",
                    api_key="testkey",
                    model="whisper-1",
                    language="en",
                    hints_file=str(custom_hints),
                    post_process=True,
                    temperature=0.3,
                    verify_ssl=True,
                )
            )
        )

        provider = create_provider(config)
        assert provider.model == "whisper-1"
        assert provider.language == "en"
        assert provider.post_process is True
        assert provider.temperature == 0.3
        assert provider.verify_ssl is True
        assert provider.hints == "Custom vocabulary: TestApp"

    def test_verify_ssl_false_logs_warning(self, caplog):
        with caplog.at_level("WARNING"):
            p = OpenAICompatibleProvider(
                base_url="http://localhost:8000/v1",
                api_key="testkey",
                model="whisper-1",
                verify_ssl=False,
            )
        assert p.verify_ssl is False
        assert "SSL verification is disabled" in caplog.text

    def test_verify_ssl_true_no_warning(self, caplog):
        with caplog.at_level("WARNING"):
            p = OpenAICompatibleProvider(
                base_url="http://localhost:8000/v1",
                api_key="testkey",
                model="whisper-1",
                verify_ssl=True,
            )
        assert p.verify_ssl is True
        assert "SSL verification is disabled" not in caplog.text

    def test_empty_transcript_returns_empty_string(self, monkeypatch):
        audio = np.zeros((16000, 1), dtype=np.int16)
        p = OpenAICompatibleProvider(
            base_url="http://localhost:8000/v1",
            api_key="testkey",
            model="whisper-1",
            post_process=True,
        )

        class FakeResult:
            text = ""

        class FakeTranscriptions:
            def create(self, **kwargs):
                return FakeResult()

        class FakeAudio:
            transcriptions = FakeTranscriptions()

        class FakeClient:
            audio = FakeAudio()

        p.client = FakeClient()
        result = p.transcribe(audio)
        assert result == ""
