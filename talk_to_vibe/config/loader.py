from pathlib import Path
from typing import Optional

import yaml

from talk_to_vibe.config.constants import CONFIG_DIR, CONFIG_FILE, DEFAULT_PTT_KEY
from talk_to_vibe.config.models import (
    AppConfig,
    ProviderConfig,
    GroqConfig,
    OpenAIConfig,
    OpenAICompatibleConfig,
    OpenRouterConfig,
    LocalWhisperConfig,
)
from talk_to_vibe.errors import ConfigError


def load_config(path: Optional[Path] = None) -> AppConfig:
    config_path = path or CONFIG_FILE
    if not config_path.exists():
        return AppConfig()
    try:
        raw = yaml.safe_load(config_path.read_text())
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {config_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"Expected dict at top level in {config_path}")
    return _dict_to_config(raw)


def save_config(config: AppConfig, path: Optional[Path] = None) -> None:
    config_path = path or CONFIG_FILE
    config_path.parent.mkdir(parents=True, exist_ok=True)
    content = _config_to_yaml(config)
    config_path.write_text(content)
    try:
        config_path.chmod(0o600)
    except OSError:
        pass


def _dict_to_config(raw: dict) -> AppConfig:
    providers_raw = raw.get("providers", {})
    groq_raw = providers_raw.get("groq", {})
    openai_raw = providers_raw.get("openai", {})
    compat_raw = providers_raw.get("openai_compatible", {})
    openrouter_raw = providers_raw.get("openrouter", {})
    local_whisper_raw = providers_raw.get("local_whisper", {})

    mic_prefs_raw = raw.get("mic_preferences") or []
    if isinstance(mic_prefs_raw, str):
        mic_prefs_raw = [mic_prefs_raw]
    mic_preferences = [str(p).strip() for p in mic_prefs_raw if str(p).strip()]

    return AppConfig(
        provider=raw.get("provider", "groq"),
        ptt_key=raw.get("ptt_key", DEFAULT_PTT_KEY),
        auto_enter=raw.get("auto_enter", False),
        prompt_file=raw.get("prompt_file", ""),
        mic_preferences=mic_preferences,
        providers=ProviderConfig(
            groq=GroqConfig(**{k: v for k, v in (groq_raw or {}).items() if k in GroqConfig.__dataclass_fields__}),
            openai=OpenAIConfig(**{k: v for k, v in (openai_raw or {}).items() if k in OpenAIConfig.__dataclass_fields__}),
            openai_compatible=OpenAICompatibleConfig(**{k: v for k, v in (compat_raw or {}).items() if k in OpenAICompatibleConfig.__dataclass_fields__}),
            openrouter=OpenRouterConfig(**{k: v for k, v in (openrouter_raw or {}).items() if k in OpenRouterConfig.__dataclass_fields__}),
            local_whisper=LocalWhisperConfig(**{k: v for k, v in (local_whisper_raw or {}).items() if k in LocalWhisperConfig.__dataclass_fields__}),
        ),
    )


def _config_to_yaml(config: AppConfig) -> str:
    lines = []
    lines.append(f"provider: {_yaml_val(config.provider)}")
    lines.append(f"ptt_key: {_yaml_val(config.ptt_key)}")
    lines.append(f"auto_enter: {_yaml_val(config.auto_enter)}")
    if config.prompt_file:
        lines.append(f"prompt_file: {_yaml_val(config.prompt_file)}")
    else:
        lines.append("# prompt_file: ~/my_prompt.md  # Override the bundled transcription prompt with a custom .md file")
    if config.mic_preferences:
        lines.append("mic_preferences:")
        for pref in config.mic_preferences:
            lines.append(f"  - {_yaml_val(pref)}")
    else:
        lines.append("# mic_preferences:                 # Priority list of mic name substrings (case-insensitive)")
        lines.append("#   - \"TONOR TC30\"               # First match wins; falls through to system defaults if none match.")
        lines.append("#   - \"NexiGo\"                   # Useful for KVM/USB hot-plug — re-evaluated on every recording.")
    lines.append("")
    lines.append("providers:")
    lines.append("  groq:")
    lines.append(f"    api_key: {_yaml_val(config.providers.groq.api_key)}")
    lines.append(f"    model: {_yaml_val(config.providers.groq.model)}")
    lines.append("  openai:")
    if config.provider == "openai":
        lines.append(f"    api_key: {_yaml_val(config.providers.openai.api_key)}")
        lines.append(f"    model: {_yaml_val(config.providers.openai.model)}")
    else:
        lines.append(f"    # api_key: sk-...")
        lines.append(f"    # model: whisper-1")
    lines.append("  openai_compatible:")
    if config.provider == "openai_compatible":
        lines.append(f"    base_url: {_yaml_val(config.providers.openai_compatible.base_url)}")
        lines.append(f"    api_key: {_yaml_val(config.providers.openai_compatible.api_key)}")
        lines.append(f"    model: {_yaml_val(config.providers.openai_compatible.model)}")
    else:
        lines.append(f"    # base_url: http://localhost:8000/v1")
        lines.append(f"    # api_key: \"\"")
        lines.append(f"    # model: whisper-1")
    lines.append("  openrouter:")
    if config.provider == "openrouter":
        lines.append(f"    api_key: {_yaml_val(config.providers.openrouter.api_key)}")
        lines.append(f"    model: {_yaml_val(config.providers.openrouter.model)}")
        lines.append(f"    base_url: {_yaml_val(config.providers.openrouter.base_url)}")
    else:
        lines.append(f"    # api_key: sk-or-...")
        lines.append(f"    # model: google/gemini-3.1-flash-lite-preview")
        lines.append(f"    # base_url: https://openrouter.ai/api/v1/chat/completions")
    lines.append("  local_whisper:")
    if config.provider == "local_whisper":
        lw = config.providers.local_whisper
        lines.append(f"    model_size: {_yaml_val(lw.model_size)}")
        lines.append(f"    device: {_yaml_val(lw.device)}")
        lines.append(f"    compute_type: {_yaml_val(lw.compute_type)}")
        lines.append(f"    language: {_yaml_val(lw.language)}")
        if lw.model_dir:
            lines.append(f"    model_dir: {_yaml_val(lw.model_dir)}")
        else:
            lines.append(f"    # model_dir: /path/to/local/model  # Override HF cache location")
        lines.append(f"    cpu_threads: {_yaml_val(lw.cpu_threads)}")
        lines.append(f"    beam_size: {_yaml_val(lw.beam_size)}")
        lines.append(f"    vad_filter: {_yaml_val(lw.vad_filter)}")
    else:
        lines.append(f"    # model_size: large-v3-turbo")
        lines.append(f"    # device: auto         # auto, cuda, cpu")
        lines.append(f"    # compute_type: auto   # auto, float16, int8_float16, int8")
        lines.append(f"    # language: en")
        lines.append(f"    # vad_filter: true")
    lines.append("")
    return "\n".join(lines) + "\n"


def _yaml_val(val) -> str:
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, str) and (not val or " " in val or ":" in val or "#" in val):
        return f'"{val}"'
    if isinstance(val, str):
        return val
    return str(val)
