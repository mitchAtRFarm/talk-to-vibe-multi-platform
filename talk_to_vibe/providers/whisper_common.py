from talk_to_vibe.providers.post_process import clean_transcript
from talk_to_vibe.providers.prompts import load_custom_prompt, load_prompt


def load_whisper_hints(hints_file: str) -> str:
    try:
        if hints_file:
            return load_custom_prompt(hints_file)
        return load_prompt("whisper_hints")
    except FileNotFoundError:
        return ""


def finalize_whisper_text(text: str, post_process: bool) -> str:
    result = text.strip()
    if post_process and result:
        result = clean_transcript(result)
    return result
