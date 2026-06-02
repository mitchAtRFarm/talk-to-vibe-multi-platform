import logging
import os

import httpx
import numpy as np

from talk_to_vibe.providers.base import BaseSTTProvider
from talk_to_vibe.audio.wav import audio_to_wav_file
from talk_to_vibe.providers.whisper_common import finalize_whisper_text, load_whisper_hints


logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(BaseSTTProvider):
    provider_name = "OpenAI-Compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        language: str = "",
        hints_file: str = "",
        post_process: bool = True,
        temperature: float = 0,
        verify_ssl: bool = True,
    ):
        from openai import OpenAI
        if not api_key:
            logger.warning(
                "No API key configured for OpenAI-Compatible provider; using fallback token for unauthenticated endpoints."
            )
        client_kwargs = {
            "base_url": base_url,
            "api_key": api_key or "not-needed",
        }
        if not verify_ssl:
            client_kwargs["http_client"] = httpx.Client(verify=False)
            logger.warning(
                "SSL verification is disabled for OpenAI-Compatible provider (verify_ssl=false)."
            )
        self.client = OpenAI(**client_kwargs)
        self.model = model
        self.language = language
        self.hints = load_whisper_hints(hints_file)
        self.post_process = post_process
        self.temperature = temperature
        self.verify_ssl = verify_ssl

    def transcribe(self, audio_data: np.ndarray) -> str:
        wav_path = audio_to_wav_file(audio_data)
        try:
            with open(wav_path, "rb") as f:
                kwargs = {
                    "model": self.model,
                    "file": f,
                    "temperature": self.temperature,
                }
                if self.language:
                    kwargs["language"] = self.language
                if self.hints:
                    kwargs["prompt"] = self.hints
                result = self.client.audio.transcriptions.create(**kwargs)
            return finalize_whisper_text(result.text, self.post_process)
        finally:
            os.unlink(wav_path)
