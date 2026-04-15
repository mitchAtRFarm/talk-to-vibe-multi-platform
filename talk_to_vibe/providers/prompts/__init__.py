from functools import lru_cache
from importlib import resources
from pathlib import Path


@lru_cache(maxsize=8)
def load_prompt(name: str) -> str:
    resource_name = f"{name}.md"
    try:
        return resources.files(__package__).joinpath(resource_name).read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Prompt file not found: {resource_name}") from exc


def load_custom_prompt(path_str: str) -> str:
    path = Path(path_str).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Custom prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()
