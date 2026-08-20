import pytest
import yaml

from talk_to_vibe.config.loader import _config_to_yaml, _dict_to_config, load_config, save_config
from talk_to_vibe.config.models import (
    AppConfig,
    OpenAICompatibleConfig,
    OpenAIConfig,
    OpenRouterConfig,
    OpenRouterWhisperConfig,
    ProviderConfig,
)
from talk_to_vibe.errors import ConfigError


class TestAppConfigDefaults:
    def test_default_provider_is_openrouter_whisper(self):
        cfg = AppConfig()
        assert cfg.provider == "openrouter_whisper"

    def test_default_ptt_key_is_f18(self):
        cfg = AppConfig()
        assert cfg.ptt_key == "ctrl+9"

    def test_default_auto_enter_is_false(self):
        cfg = AppConfig()
        assert cfg.auto_enter is False

    def test_default_prompt_file_is_empty(self):
        cfg = AppConfig()
        assert cfg.prompt_file == ""

    def test_default_provider_configs_exist(self):
        cfg = AppConfig()
        assert isinstance(cfg.providers.openrouter_whisper, OpenRouterWhisperConfig)
        assert isinstance(cfg.providers.openai, OpenAIConfig)
        assert isinstance(cfg.providers.openai_compatible, OpenAICompatibleConfig)
        assert isinstance(cfg.providers.openrouter, OpenRouterConfig)

    def test_default_models_are_in_config(self):
        cfg = AppConfig()
        assert cfg.providers.openrouter_whisper.model == "x-ai/grok-stt-1.0"
        assert cfg.providers.openai.model == "whisper-1"
        assert cfg.providers.openai_compatible.model == "whisper-1"
        assert cfg.providers.openrouter.model == "google/gemini-3.1-flash-lite-preview"

    def test_default_base_urls_are_in_config(self):
        cfg = AppConfig()
        assert cfg.providers.openrouter_whisper.base_url == "https://openrouter.ai/api/v1/audio/transcriptions"
        assert cfg.providers.openrouter.base_url == "https://openrouter.ai/api/v1/chat/completions"


class TestAppConfigValidation:
    def test_valid_openrouter_whisper_config(self):
        cfg = AppConfig(
            provider="openrouter_whisper",
            providers=ProviderConfig(openrouter_whisper=OpenRouterWhisperConfig(api_key="sk-or-test")),
        )
        assert cfg.validate() == []

    def test_valid_openai_config(self):
        cfg = AppConfig(provider="openai", providers=ProviderConfig(openai=OpenAIConfig(api_key="sk_test")))
        assert cfg.validate() == []

    def test_valid_openai_compatible_config(self):
        cfg = AppConfig(provider="openai_compatible", providers=ProviderConfig(openai_compatible=OpenAICompatibleConfig(base_url="http://localhost:8000/v1")))
        assert cfg.validate() == []

    def test_valid_openrouter_config(self):
        cfg = AppConfig(provider="openrouter", providers=ProviderConfig(openrouter=OpenRouterConfig(api_key="sk-or-test")))
        assert cfg.validate() == []

    def test_valid_openrouter_priority_service_tier(self):
        cfg = AppConfig(
            provider="openrouter",
            providers=ProviderConfig(openrouter=OpenRouterConfig(api_key="sk-or-test", service_tier="priority")),
        )
        assert cfg.validate() == []

    def test_missing_openrouter_whisper_api_key(self):
        cfg = AppConfig(provider="openrouter_whisper")
        errors = cfg.validate()
        assert any("OpenRouter API key" in e for e in errors)

    def test_missing_openai_api_key(self):
        cfg = AppConfig(provider="openai")
        errors = cfg.validate()
        assert any("OpenAI API key" in e for e in errors)

    def test_missing_openai_compatible_base_url(self):
        cfg = AppConfig(provider="openai_compatible")
        errors = cfg.validate()
        assert any("Base URL" in e for e in errors)

    def test_missing_openrouter_api_key(self):
        cfg = AppConfig(provider="openrouter")
        errors = cfg.validate()
        assert any("OpenRouter API key" in e for e in errors)

    def test_unknown_provider(self):
        cfg = AppConfig(provider="bogus")
        errors = cfg.validate()
        assert any("Unknown provider" in e for e in errors)

    def test_missing_openrouter_model(self):
        cfg = AppConfig(provider="openrouter", providers=ProviderConfig(openrouter=OpenRouterConfig(api_key="sk-or-test", model="")))
        errors = cfg.validate()
        assert any("OpenRouter model" in e for e in errors)

    def test_missing_openrouter_base_url(self):
        cfg = AppConfig(provider="openrouter", providers=ProviderConfig(openrouter=OpenRouterConfig(api_key="sk-or-test", base_url="")))
        errors = cfg.validate()
        assert any("OpenRouter base URL" in e for e in errors)

    def test_missing_openrouter_whisper_model(self):
        cfg = AppConfig(
            provider="openrouter_whisper",
            providers=ProviderConfig(openrouter_whisper=OpenRouterWhisperConfig(api_key="sk-or-test", model="")),
        )
        errors = cfg.validate()
        assert any("OpenRouter STT model" in e for e in errors)


class TestLoadConfig:
    def test_load_missing_file_returns_defaults(self, tmp_path):
        cfg = load_config(tmp_path / "nonexistent.yaml")
        assert cfg.provider == "openrouter_whisper"
        assert cfg.ptt_key == "ctrl+9"
        assert cfg.prompt_file == ""

    def test_load_valid_yaml(self, tmp_path):
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump({
            "provider": "openrouter",
            "ptt_key": "f19",
            "auto_enter": True,
            "providers": {
                "openrouter": {"api_key": "sk-or-test123", "model": "google/gemini-3.1-flash-lite-preview", "base_url": "https://openrouter.ai/api/v1/chat/completions"},
            },
        }))
        cfg = load_config(p)
        assert cfg.provider == "openrouter"
        assert cfg.ptt_key == "f19"
        assert cfg.auto_enter is True
        assert cfg.providers.openrouter.api_key == "sk-or-test123"

    def test_load_openrouter_whisper(self, tmp_path):
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump({
            "provider": "openrouter_whisper",
            "providers": {
                "openrouter_whisper": {
                    "api_key": "sk-or-test123",
                    "model": "openai/whisper-large-v3",
                    "base_url": "https://openrouter.ai/api/v1/audio/transcriptions",
                    "language": "en",
                    "post_process": False,
                    "temperature": 0.2,
                    "hint_provider_slug": "groq",
                },
            },
        }))
        cfg = load_config(p)
        assert cfg.providers.openrouter_whisper.api_key == "sk-or-test123"
        assert cfg.providers.openrouter_whisper.model == "openai/whisper-large-v3"
        assert cfg.providers.openrouter_whisper.language == "en"
        assert cfg.providers.openrouter_whisper.post_process is False
        assert cfg.providers.openrouter_whisper.temperature == 0.2

    def test_load_openrouter_service_tier(self, tmp_path):
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump({
            "provider": "openrouter",
            "providers": {
                "openrouter": {
                    "api_key": "sk-or-test123",
                    "model": "google/gemini-3.1-flash-lite-preview",
                    "base_url": "https://openrouter.ai/api/v1/chat/completions",
                    "service_tier": "priority",
                },
            },
        }))
        cfg = load_config(p)
        assert cfg.providers.openrouter.service_tier == "priority"

    def test_load_prompt_file(self, tmp_path):
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump({
            "provider": "openrouter_whisper",
            "prompt_file": "~/my_prompt.md",
            "providers": {"openrouter_whisper": {"api_key": "sk-or-test"}},
        }))
        cfg = load_config(p)
        assert cfg.prompt_file == "~/my_prompt.md"

    def test_load_invalid_yaml_raises(self, tmp_path):
        p = tmp_path / "config.yaml"
        p.write_text("{{{{invalid yaml")
        with pytest.raises(ConfigError, match="Invalid YAML"):
            load_config(p)

    def test_load_non_dict_yaml_raises(self, tmp_path):
        p = tmp_path / "config.yaml"
        p.write_text("42")
        with pytest.raises(ConfigError, match="Expected dict"):
            load_config(p)

    def test_load_partial_config_fills_defaults(self, tmp_path):
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump({"provider": "openai"}))
        cfg = load_config(p)
        assert cfg.provider == "openai"
        assert cfg.ptt_key == "ctrl+9"
        assert cfg.auto_enter is False
        assert cfg.prompt_file == ""
        assert cfg.providers.openai.model == "whisper-1"

    def test_load_openai_compatible_with_all_fields(self, tmp_path):
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump({
            "provider": "openai_compatible",
            "providers": {
                "openai_compatible": {
                    "base_url": "http://localhost:8000/v1",
                    "api_key": "testkey",
                    "model": "whisper-1",
                    "language": "en",
                    "hints_file": "/path/to/hints.md",
                    "post_process": False,
                    "temperature": 0.5,
                    "verify_ssl": False,
                },
            },
        }))
        cfg = load_config(p)
        assert cfg.provider == "openai_compatible"
        assert cfg.providers.openai_compatible.base_url == "http://localhost:8000/v1"
        assert cfg.providers.openai_compatible.api_key == "testkey"
        assert cfg.providers.openai_compatible.model == "whisper-1"
        assert cfg.providers.openai_compatible.language == "en"
        assert cfg.providers.openai_compatible.hints_file == "/path/to/hints.md"
        assert cfg.providers.openai_compatible.post_process is False
        assert cfg.providers.openai_compatible.temperature == 0.5
        assert cfg.providers.openai_compatible.verify_ssl is False

    def test_load_openai_compatible_missing_verify_ssl_defaults_to_true(self, tmp_path):
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump({
            "provider": "openai_compatible",
            "providers": {
                "openai_compatible": {
                    "base_url": "http://localhost:8000/v1",
                    "api_key": "testkey",
                    "model": "whisper-1",
                },
            },
        }))
        cfg = load_config(p)
        assert cfg.providers.openai_compatible.verify_ssl is True


class TestSaveConfig:
    def test_save_creates_file(self, tmp_path):
        p = tmp_path / "sub" / "config.yaml"
        cfg = AppConfig(provider="openrouter", ptt_key="f19", auto_enter=True, providers=ProviderConfig(openrouter=OpenRouterConfig(api_key="sk-or-test")))
        save_config(cfg, path=p)
        assert p.exists()
        raw = yaml.safe_load(p.read_text())
        assert raw["provider"] == "openrouter"
        assert raw["ptt_key"] == "f19"
        assert raw["auto_enter"] is True

    def test_roundtrip_save_load(self, tmp_path):
        p = tmp_path / "config.yaml"
        original = AppConfig(
            provider="openrouter_whisper",
            ptt_key="cmd_r",
            auto_enter=True,
            providers=ProviderConfig(
                openrouter_whisper=OpenRouterWhisperConfig(
                    api_key="sk-or-abc123",
                    model="openai/whisper-large-v3",
                    language="en",
                ),
            ),
        )
        save_config(original, path=p)
        loaded = load_config(p)
        assert loaded.provider == original.provider
        assert loaded.ptt_key == original.ptt_key
        assert loaded.auto_enter == original.auto_enter
        assert loaded.providers.openrouter_whisper.api_key == original.providers.openrouter_whisper.api_key
        assert loaded.providers.openrouter_whisper.model == original.providers.openrouter_whisper.model

    def test_roundtrip_prompt_file(self, tmp_path):
        p = tmp_path / "config.yaml"
        original = AppConfig(
            provider="openrouter_whisper",
            prompt_file="~/my_prompt.md",
            providers=ProviderConfig(openrouter_whisper=OpenRouterWhisperConfig(api_key="sk-or-test")),
        )
        save_config(original, path=p)
        loaded = load_config(p)
        assert loaded.prompt_file == "~/my_prompt.md"

    def test_saved_yaml_has_commented_prompt_file_when_empty(self, tmp_path):
        p = tmp_path / "config.yaml"
        cfg = AppConfig(provider="openrouter_whisper", providers=ProviderConfig(openrouter_whisper=OpenRouterWhisperConfig(api_key="sk-or-test")))
        save_config(cfg, path=p)
        content = p.read_text()
        assert "# prompt_file:" in content

    def test_saved_yaml_has_active_prompt_file_when_set(self, tmp_path):
        p = tmp_path / "config.yaml"
        cfg = AppConfig(
            provider="openrouter_whisper",
            prompt_file="~/my_prompt.md",
            providers=ProviderConfig(openrouter_whisper=OpenRouterWhisperConfig(api_key="sk-or-test")),
        )
        save_config(cfg, path=p)
        content = p.read_text()
        assert "prompt_file: ~/my_prompt.md" in content
        assert "# prompt_file:" not in content

    def test_saved_yaml_has_commented_inactive_providers(self, tmp_path):
        p = tmp_path / "config.yaml"
        cfg = AppConfig(provider="openrouter_whisper", providers=ProviderConfig(openrouter_whisper=OpenRouterWhisperConfig(api_key="sk-or-test")))
        save_config(cfg, path=p)
        content = p.read_text()
        assert "# api_key: sk-..." in content
        assert "# base_url: http://localhost:8000/v1" in content
        assert "api_key: sk-or-test" in content

    def test_saved_yaml_has_active_provider_uncommented(self, tmp_path):
        p = tmp_path / "config.yaml"
        cfg = AppConfig(
            provider="openrouter_whisper",
            providers=ProviderConfig(openrouter_whisper=OpenRouterWhisperConfig(api_key="sk-or-real", post_process=False)),
        )
        save_config(cfg, path=p)
        content = p.read_text()
        lines = content.split("\n")
        openrouter_whisper_section = False
        for line in lines:
            if "openrouter_whisper:" in line and not line.strip().startswith("#"):
                openrouter_whisper_section = True
            if openrouter_whisper_section and "api_key:" in line and not line.strip().startswith("#"):
                assert "sk-or-real" in line
                break
        assert "post_process: false" in content

    def test_roundtrip_openai_compatible_with_all_fields(self, tmp_path):
        p = tmp_path / "config.yaml"
        original = AppConfig(
            provider="openai_compatible",
            providers=ProviderConfig(
                openai_compatible=OpenAICompatibleConfig(
                    base_url="http://localhost:8000/v1",
                    api_key="testkey",
                    model="whisper-1",
                    language="en",
                    hints_file="/path/to/hints.md",
                    post_process=False,
                    temperature=0.5,
                    verify_ssl=False,
                ),
            ),
        )
        save_config(original, path=p)
        loaded = load_config(p)
        assert loaded.provider == original.provider
        assert loaded.providers.openai_compatible.base_url == original.providers.openai_compatible.base_url
        assert loaded.providers.openai_compatible.api_key == original.providers.openai_compatible.api_key
        assert loaded.providers.openai_compatible.model == original.providers.openai_compatible.model
        assert loaded.providers.openai_compatible.language == original.providers.openai_compatible.language
        assert loaded.providers.openai_compatible.hints_file == original.providers.openai_compatible.hints_file
        assert loaded.providers.openai_compatible.post_process == original.providers.openai_compatible.post_process
        assert loaded.providers.openai_compatible.temperature == original.providers.openai_compatible.temperature
        assert loaded.providers.openai_compatible.verify_ssl == original.providers.openai_compatible.verify_ssl


class TestConfigToYaml:
    def test_includes_all_provider_sections(self):
        cfg = AppConfig()
        result = _config_to_yaml(cfg)
        assert "openrouter_whisper:" in result
        assert "openai:" in result
        assert "openai_compatible:" in result
        assert "openrouter:" in result

    def test_includes_prompt_file(self):
        cfg = AppConfig(prompt_file="/path/to/prompt.md")
        result = _config_to_yaml(cfg)
        assert "prompt_file: /path/to/prompt.md" in result

    def test_includes_openrouter_service_tier(self):
        cfg = AppConfig(
            provider="openrouter",
            providers=ProviderConfig(openrouter=OpenRouterConfig(api_key="sk-or-test", service_tier="priority")),
        )
        result = _config_to_yaml(cfg)
        assert "service_tier: priority" in result

    def test_commented_prompt_file_when_empty(self):
        cfg = AppConfig(prompt_file="")
        result = _config_to_yaml(cfg)
        assert "# prompt_file:" in result

    def test_active_openai_compatible_includes_all_fields(self):
        cfg = AppConfig(
            provider="openai_compatible",
            providers=ProviderConfig(
                openai_compatible=OpenAICompatibleConfig(
                    base_url="http://localhost:8000/v1",
                    api_key="testkey",
                    model="whisper-1",
                    language="en",
                    hints_file="/path/to/hints.md",
                    post_process=True,
                    temperature=0.3,
                    verify_ssl=False,
                ),
            ),
        )
        result = _config_to_yaml(cfg)
        assert 'base_url: "http://localhost:8000/v1"' in result
        assert "api_key: testkey" in result
        assert "model: whisper-1" in result
        assert "language: en" in result
        assert "hints_file: /path/to/hints.md" in result
        assert "post_process: true" in result
        assert "temperature: 0.3" in result
        assert "verify_ssl: false" in result

    def test_inactive_openai_compatible_has_commented_fields(self):
        cfg = AppConfig(provider="openrouter_whisper")
        result = _config_to_yaml(cfg)
        assert "# base_url: http://localhost:8000/v1" in result
        assert "# api_key:" in result
        assert "# model: whisper-1" in result
        assert "# language:" in result
        assert "# post_process: true" in result
        assert "# temperature: 0" in result
        assert "# hints_file:" in result
        assert "# verify_ssl: true" in result

    def test_active_openai_compatible_verify_ssl_false(self):
        cfg = AppConfig(
            provider="openai_compatible",
            providers=ProviderConfig(
                openai_compatible=OpenAICompatibleConfig(
                    base_url="http://localhost:8000/v1",
                    api_key="testkey",
                    model="whisper-1",
                    verify_ssl=False,
                ),
            ),
        )
        result = _config_to_yaml(cfg)
        assert "verify_ssl: false" in result


class TestDictToConfig:
    def test_ignores_extra_keys(self):
        raw = {
            "provider": "openrouter_whisper",
            "ptt_key": "alt_r",
            "auto_enter": False,
            "prompt_file": "",
            "providers": {
                "openrouter_whisper": {"api_key": "sk-or-test", "model": "openai/whisper-large-v3-turbo", "extra": "ignored"},
            },
        }
        cfg = _dict_to_config(raw)
        assert cfg.providers.openrouter_whisper.api_key == "sk-or-test"
