import re
from abc import ABC, abstractmethod
from typing import Iterator

import numpy as np


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


class BaseSTTProvider(ABC):
    provider_name: str = "unknown"
    model: str = ""

    @abstractmethod
    def transcribe(self, audio_data: np.ndarray) -> str:
        ...

    def transcribe_stream(self, audio_data: np.ndarray) -> Iterator[str]:
        """Yield transcript pieces as they become available.

        Default implementation runs the synchronous transcribe() and splits
        the result on sentence boundaries so the paste pipeline can show
        progress consistently across providers. Subclasses with a streaming
        backend (e.g. faster-whisper segments) should override this.
        """
        text = self.transcribe(audio_data).strip()
        if not text:
            return
        parts = [p for p in _SENTENCE_SPLIT.split(text) if p]
        for part in parts:
            yield part
