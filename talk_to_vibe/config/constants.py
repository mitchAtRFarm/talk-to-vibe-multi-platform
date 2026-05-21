from pathlib import Path

CONFIG_DIR = Path.home() / ".talktovibe"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

DEFAULT_PROVIDER = "openrouter_whisper"
DEFAULT_PTT_KEY = "ctrl+9"

SUPPORTED_PROVIDERS = ["openrouter_whisper", "openai", "openai_compatible", "openrouter", "local_whisper"]
