import logging
import os

import numpy as np

from talk_to_vibe.providers.base import BaseSTTProvider
from talk_to_vibe.audio.wav import audio_to_wav_file


logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(BaseSTTProvider):
    provider_name = "OpenAI-Compatible"

    def __init__(self, base_url: str, api_key: str, model: str):
        from openai import OpenAI
        if not api_key:
            logger.warning(
                "No API key configured for OpenAI-Compatible provider; using fallback token for unauthenticated endpoints."
            )
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key or "not-needed",
        )
        self.model = model

    def transcribe(self, audio_data: np.ndarray) -> str:
        wav_path = audio_to_wav_file(audio_data)
        try:
            with open(wav_path, "rb") as f:
                result = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=f,
                )
            return result.text.strip()
        finally:
            os.unlink(wav_path)
