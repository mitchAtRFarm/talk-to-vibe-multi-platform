import pytest

from talk_to_vibe.config.models import (
    AppConfig,
    OpenAICompatibleConfig,
    OpenAIConfig,
    OpenRouterConfig,
    OpenRouterWhisperConfig,
    ProviderConfig,
)
from talk_to_vibe.errors import ProviderAuthError, ProviderError
from talk_to_vibe.providers.factory import create_provider
from talk_to_vibe.providers.openai_compatible import OpenAICompatibleProvider
from talk_to_vibe.providers.openai_whisper import OpenAIWhisperProvider
from talk_to_vibe.providers.openrouter_multimodal import OpenRouterMultimodalProvider
from talk_to_vibe.providers.openrouter_whisper import OpenRouterWhisperProvider


class TestCreateProvider:
    def test_openrouter_whisper_provider(self):
        cfg = AppConfig(
            provider="openrouter_whisper",
            providers=ProviderConfig(
                openrouter_whisper=OpenRouterWhisperConfig(api_key="sk-or-test")
            ),
        )
        p = create_provider(cfg)
        assert isinstance(p, OpenRouterWhisperProvider)
        assert p.provider_name == "OpenRouter Whisper"
        assert p.model == "openai/whisper-large-v3-turbo"
        assert p.base_url == "https://openrouter.ai/api/v1/audio/transcriptions"

    def test_openai_provider(self):
        cfg = AppConfig(provider="openai", providers=ProviderConfig(openai=OpenAIConfig(api_key="sk_test")))
        p = create_provider(cfg)
        assert isinstance(p, OpenAIWhisperProvider)
        assert p.provider_name == "OpenAI"
        assert p.model == "whisper-1"

    def test_openai_compatible_provider(self):
        cfg = AppConfig(
            provider="openai_compatible",
            providers=ProviderConfig(
                openai_compatible=OpenAICompatibleConfig(base_url="http://localhost:8000/v1", api_key="key")
            ),
        )
        p = create_provider(cfg)
        assert isinstance(p, OpenAICompatibleProvider)
        assert p.provider_name == "OpenAI-Compatible"
        assert p.model == "whisper-1"
        assert str(p.client.base_url).rstrip("/") == "http://localhost:8000/v1"

    def test_openrouter_provider(self):
        cfg = AppConfig(provider="openrouter", providers=ProviderConfig(openrouter=OpenRouterConfig(api_key="sk-or-test")))
        p = create_provider(cfg)
        assert isinstance(p, OpenRouterMultimodalProvider)
        assert p.provider_name == "OpenRouter"
        assert p.model == "google/gemini-3.1-flash-lite-preview"
        assert p.base_url == "https://openrouter.ai/api/v1/chat/completions"
        assert p.service_tier == ""

    def test_unknown_provider_raises(self):
        cfg = AppConfig(provider="bogus")
        with pytest.raises(ProviderError, match="Unknown provider"):
            create_provider(cfg)

    def test_missing_openrouter_whisper_key_raises(self):
        cfg = AppConfig(provider="openrouter_whisper")
        with pytest.raises(ProviderAuthError, match="OpenRouter API key") as exc:
            create_provider(cfg)
        assert "Reconfigure" in str(exc.value)

    def test_missing_openai_key_raises(self):
        cfg = AppConfig(provider="openai")
        with pytest.raises(ProviderAuthError, match="OpenAI API key"):
            create_provider(cfg)

    def test_missing_openai_compatible_base_url_raises(self):
        cfg = AppConfig(provider="openai_compatible")
        with pytest.raises(ProviderAuthError, match="Base URL"):
            create_provider(cfg)

    def test_missing_openrouter_key_raises(self):
        cfg = AppConfig(provider="openrouter")
        with pytest.raises(ProviderAuthError, match="OpenRouter API key") as exc:
            create_provider(cfg)
        assert "TalkToVibe" in str(exc.value)

    def test_openrouter_whisper_custom_fields(self):
        cfg = AppConfig(
            provider="openrouter_whisper",
            providers=ProviderConfig(
                openrouter_whisper=OpenRouterWhisperConfig(
                    api_key="sk-or-test",
                    model="openai/whisper-large-v3",
                    language="en",
                    post_process=False,
                    hint_provider_slug="groq",
                )
            ),
        )
        p = create_provider(cfg)
        assert p.model == "openai/whisper-large-v3"
        assert p.language == "en"
        assert p.post_process is False
        assert p.hint_provider_slug == "groq"

    def test_openrouter_custom_model(self):
        cfg = AppConfig(provider="openrouter", providers=ProviderConfig(openrouter=OpenRouterConfig(api_key="sk-or-test", model="google/gemini-2.5-flash")))
        p = create_provider(cfg)
        assert p.model == "google/gemini-2.5-flash"

    def test_openrouter_custom_base_url(self):
        cfg = AppConfig(provider="openrouter", providers=ProviderConfig(openrouter=OpenRouterConfig(api_key="sk-or-test", base_url="https://custom.example.com/v1/chat/completions")))
        p = create_provider(cfg)
        assert p.base_url == "https://custom.example.com/v1/chat/completions"

    def test_openrouter_custom_service_tier(self):
        cfg = AppConfig(provider="openrouter", providers=ProviderConfig(openrouter=OpenRouterConfig(api_key="sk-or-test", service_tier="priority")))
        p = create_provider(cfg)
        assert p.service_tier == "priority"
