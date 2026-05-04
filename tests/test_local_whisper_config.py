import yaml

from talk_to_vibe.config.loader import load_config, save_config
from talk_to_vibe.config.models import (
    AppConfig,
    LocalWhisperConfig,
    ProviderConfig,
)


class TestLocalWhisperDefaults:
    def test_default_model_size_is_large_v3_turbo(self):
        cfg = AppConfig()
        assert cfg.providers.local_whisper.model_size == "large-v3-turbo"

    def test_default_device_is_auto(self):
        cfg = AppConfig()
        assert cfg.providers.local_whisper.device == "auto"

    def test_default_compute_type_is_auto(self):
        cfg = AppConfig()
        assert cfg.providers.local_whisper.compute_type == "auto"


class TestLocalWhisperValidation:
    def test_valid_default_local_whisper_config(self):
        cfg = AppConfig(provider="local_whisper")
        assert cfg.validate() == []

    def test_invalid_device_rejected(self):
        cfg = AppConfig(
            provider="local_whisper",
            providers=ProviderConfig(local_whisper=LocalWhisperConfig(device="metal")),
        )
        errors = cfg.validate()
        assert any("device" in e for e in errors)

    def test_invalid_compute_type_rejected(self):
        cfg = AppConfig(
            provider="local_whisper",
            providers=ProviderConfig(local_whisper=LocalWhisperConfig(compute_type="float8")),
        )
        errors = cfg.validate()
        assert any("compute_type" in e for e in errors)

    def test_local_whisper_in_supported_providers(self):
        from talk_to_vibe.config.constants import SUPPORTED_PROVIDERS
        assert "local_whisper" in SUPPORTED_PROVIDERS


class TestLocalWhisperRoundtrip:
    def test_roundtrip_save_load(self, tmp_path):
        p = tmp_path / "config.yaml"
        original = AppConfig(
            provider="local_whisper",
            providers=ProviderConfig(
                local_whisper=LocalWhisperConfig(
                    model_size="large-v3-turbo",
                    device="cuda",
                    compute_type="float16",
                    language="en",
                    beam_size=3,
                    vad_filter=False,
                )
            ),
        )
        save_config(original, path=p)
        loaded = load_config(p)
        assert loaded.provider == "local_whisper"
        assert loaded.providers.local_whisper.model_size == "large-v3-turbo"
        assert loaded.providers.local_whisper.device == "cuda"
        assert loaded.providers.local_whisper.compute_type == "float16"
        assert loaded.providers.local_whisper.beam_size == 3
        assert loaded.providers.local_whisper.vad_filter is False

    def test_load_partial_local_whisper_config_fills_defaults(self, tmp_path):
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump({
            "provider": "local_whisper",
            "providers": {"local_whisper": {"model_size": "small"}},
        }))
        cfg = load_config(p)
        assert cfg.providers.local_whisper.model_size == "small"
        assert cfg.providers.local_whisper.device == "auto"
        assert cfg.providers.local_whisper.compute_type == "auto"

    def test_inactive_local_whisper_section_is_commented(self, tmp_path):
        p = tmp_path / "config.yaml"
        cfg = AppConfig(provider="groq")
        cfg.providers.groq.api_key = "gsk_test"
        save_config(cfg, path=p)
        content = p.read_text()
        assert "# model_size: large-v3-turbo" in content
        assert "# device: auto" in content


class TestLocalWhisperFactory:
    def test_local_whisper_in_registry(self):
        from talk_to_vibe.providers.factory import PROVIDER_REGISTRY
        assert "local_whisper" in PROVIDER_REGISTRY
