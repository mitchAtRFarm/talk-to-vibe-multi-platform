import base64

import numpy as np
import pytest

from talk_to_vibe.errors import ProviderError, ProviderResponseError
from talk_to_vibe.providers.openrouter_whisper import (
    OpenRouterWhisperProvider,
    uses_whisper_decoder_hints,
)


WHISPER_MODEL = "openai/whisper-large-v3-turbo"
GROK_MODEL = "x-ai/grok-stt-1.0"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1/audio/transcriptions"


def _make_provider(**kwargs):
    defaults = {
        "api_key": "sk-or-test",
        "model": WHISPER_MODEL,
        "base_url": DEFAULT_BASE_URL,
    }
    defaults.update(kwargs)
    return OpenRouterWhisperProvider(**defaults)


def _make_audio_data(duration_sec: float = 1.0, sample_rate: int = 16000) -> np.ndarray:
    samples = int(duration_sec * sample_rate)
    return np.zeros((samples, 1), dtype=np.int16)


class TestBuildPayload:
    def test_payload_structure(self):
        p = _make_provider()
        b64_audio = base64.b64encode(b"fake_wav_data").decode("utf-8")
        payload = p._build_payload(b64_audio)

        assert payload["model"] == WHISPER_MODEL
        assert payload["temperature"] == 0
        assert payload["max_tokens"] == 4096
        assert payload["input_audio"]["format"] == "wav"
        assert payload["input_audio"]["data"] == b64_audio
        assert payload["provider"]["options"]["groq"]["prompt"] == p.hints

    def test_custom_model_in_payload(self):
        p = _make_provider(model="openai/whisper-large-v3")
        payload = p._build_payload("fake_b64")
        assert payload["model"] == "openai/whisper-large-v3"

    def test_language_in_payload_when_configured(self):
        p = _make_provider(language="en")
        payload = p._build_payload("fake_b64")
        assert payload["language"] == "en"

    def test_hint_block_omitted_when_hint_provider_slug_empty(self):
        p = _make_provider(hint_provider_slug="")
        payload = p._build_payload("fake_b64")
        assert "provider" not in payload

    def test_hint_block_omitted_for_grok_even_with_groq_slug(self):
        p = _make_provider(model=GROK_MODEL, hint_provider_slug="groq")
        payload = p._build_payload("fake_b64")
        assert payload["model"] == GROK_MODEL
        assert "provider" not in payload

    def test_hint_block_omitted_for_gpt_transcribe(self):
        p = _make_provider(model="openai/gpt-4o-mini-transcribe", hint_provider_slug="groq")
        payload = p._build_payload("fake_b64")
        assert "provider" not in payload

    def test_custom_hints_file_in_payload(self, tmp_path):
        custom = tmp_path / "custom.md"
        custom.write_text("Expected vocabulary: TalkToVibe\n")
        p = _make_provider(hints_file=str(custom))
        payload = p._build_payload("fake_b64")
        assert payload["provider"]["options"]["groq"]["prompt"] == "Expected vocabulary: TalkToVibe"


class TestUsesWhisperDecoderHints:
    def test_whisper_model_with_slug(self):
        assert uses_whisper_decoder_hints(WHISPER_MODEL, "groq") is True

    def test_grok_model_with_slug(self):
        assert uses_whisper_decoder_hints(GROK_MODEL, "groq") is False

    def test_empty_slug(self):
        assert uses_whisper_decoder_hints(WHISPER_MODEL, "") is False


class TestParseResponse:
    def test_successful_transcript(self):
        p = _make_provider()

        class FakeResp:
            status_code = 200

            def json(self):
                return {"text": "Hello world"}

            text = ""

        result, seconds, tokens = p._parse_response(FakeResp())
        assert result == "Hello world"
        assert seconds == 0.0
        assert tokens == 0

    def test_usage_fields_parsed(self):
        p = _make_provider()

        class FakeResp:
            status_code = 200

            def json(self):
                return {
                    "text": "Hello world",
                    "usage": {"seconds": 9.2, "output_tokens": 30},
                }

            text = ""

        result, seconds, tokens = p._parse_response(FakeResp())
        assert result == "Hello world"
        assert seconds == 9.2
        assert tokens == 30

    def test_post_process_applied(self):
        p = _make_provider(post_process=True)

        class FakeResp:
            status_code = 200

            def json(self):
                return {"text": "Um, hello world"}

            text = ""

        result, _, _ = p._parse_response(FakeResp())
        assert result == "Hello world"

    def test_post_process_can_be_disabled(self):
        p = _make_provider(post_process=False)

        class FakeResp:
            status_code = 200

            def json(self):
                return {"text": "Um, hello world"}

            text = ""

        result, _, _ = p._parse_response(FakeResp())
        assert result == "Um, hello world"

    def test_json_error_response(self):
        p = _make_provider()

        class FakeResp:
            status_code = 401

            def json(self):
                return {"error": {"message": "Invalid API key"}}

            text = '{"error": {"message": "Invalid API key"}}'

        with pytest.raises(ProviderResponseError, match="Invalid API key"):
            p._parse_response(FakeResp())

    def test_non_json_response(self):
        p = _make_provider()

        class FakeResp:
            status_code = 200
            text = "not json at all"

            def json(self):
                raise ValueError("not json")

        with pytest.raises(ProviderResponseError, match="non-JSON"):
            p._parse_response(FakeResp())

    def test_unexpected_response_structure(self):
        p = _make_provider()

        class FakeResp:
            status_code = 200

            def json(self):
                return {"no_text": True}

            text = '{"no_text": true}'

        with pytest.raises(ProviderResponseError, match="Unexpected"):
            p._parse_response(FakeResp())


class TestTranscribeIntegration:
    def test_transcribe_builds_correct_request(self, monkeypatch):
        p = _make_provider(api_key="sk-or-testkey123", language="en", temperature=0.3)
        audio = _make_audio_data()

        captured_payload = {}

        class FakeResp:
            status_code = 200

            def json(self):
                return {"text": "test transcript"}

            text = ""

        def fake_post(url, json=None, headers=None, timeout=None):
            captured_payload["url"] = url
            captured_payload["json"] = json
            captured_payload["headers"] = headers
            captured_payload["timeout"] = timeout
            return FakeResp()

        import httpx

        monkeypatch.setattr(httpx, "post", fake_post)

        result = p.transcribe(audio)
        assert result == "test transcript"
        assert captured_payload["url"] == DEFAULT_BASE_URL
        assert captured_payload["headers"]["Authorization"] == "Bearer sk-or-testkey123"
        assert captured_payload["headers"]["Content-Type"] == "application/json"
        assert captured_payload["timeout"] == 60.0

        payload = captured_payload["json"]
        assert payload["model"] == WHISPER_MODEL
        assert payload["language"] == "en"
        assert payload["temperature"] == 0.3
        assert payload["max_tokens"] == 4096
        assert payload["input_audio"]["format"] == "wav"

        decoded = base64.b64decode(payload["input_audio"]["data"])
        assert len(decoded) > 0

    def test_transcribe_network_error(self, monkeypatch):
        p = _make_provider()
        audio = _make_audio_data()

        import httpx

        monkeypatch.setattr(httpx, "post", lambda *a, **kw: (_ for _ in ()).throw(httpx.RequestError("connection failed")))

        with pytest.raises(ProviderError, match="request failed"):
            p.transcribe(audio)

    def test_no_hardcoded_defaults_in_provider(self):
        with pytest.raises(TypeError):
            OpenRouterWhisperProvider(api_key="sk-or-test")

    def test_long_audio_sends_one_request_per_chunk(self, monkeypatch):
        p = _make_provider(model=GROK_MODEL, post_process=False)
        audio = _make_audio_data(duration_sec=25.0)
        calls = []

        class FakeResp:
            status_code = 200

            def __init__(self, text):
                self._text = text

            def json(self):
                return {"text": self._text, "usage": {"seconds": 12.0, "output_tokens": 10}}

            text = ""

        def fake_post(url, json=None, headers=None, timeout=None):
            calls.append(json)
            n = len(calls)
            return FakeResp(f"chunk {n} end words")

        import httpx

        monkeypatch.setattr(httpx, "post", fake_post)
        result = p.transcribe(audio)
        assert len(calls) == 2
        assert result == "chunk 1 end words chunk 2 end words"
