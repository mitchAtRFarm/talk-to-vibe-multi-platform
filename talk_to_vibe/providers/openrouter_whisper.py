import base64

import httpx
import numpy as np

from talk_to_vibe.audio.wav import audio_to_wav_bytes
from talk_to_vibe.errors import ProviderError, ProviderResponseError
from talk_to_vibe.providers.base import BaseSTTProvider
from talk_to_vibe.providers.whisper_common import finalize_whisper_text, load_whisper_hints


def uses_whisper_decoder_hints(model: str, hint_provider_slug: str) -> bool:
    return bool(hint_provider_slug) and "whisper" in model.lower()


class OpenRouterWhisperProvider(BaseSTTProvider):
    provider_name = "OpenRouter STT"

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        language: str = "",
        hints_file: str = "",
        post_process: bool = True,
        temperature: float = 0,
        hint_provider_slug: str = "groq",
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.language = language
        self.post_process = post_process
        self.temperature = temperature
        self.hint_provider_slug = hint_provider_slug
        self.hints = load_whisper_hints(hints_file)

    def transcribe(self, audio_data: np.ndarray) -> str:
        wav_bytes = audio_to_wav_bytes(audio_data)
        b64_audio = base64.b64encode(wav_bytes).decode("utf-8")

        payload = self._build_payload(b64_audio)
        response = self._send_request(payload)
        return self._parse_response(response)

    def _build_payload(self, b64_audio: str) -> dict:
        payload = {
            "model": self.model,
            "input_audio": {
                "data": b64_audio,
                "format": "wav",
            },
            "temperature": self.temperature,
        }
        if self.language:
            payload["language"] = self.language
        if self.hints and uses_whisper_decoder_hints(self.model, self.hint_provider_slug):
            payload["provider"] = {
                "options": {
                    self.hint_provider_slug: {
                        "prompt": self.hints,
                    }
                }
            }
        return payload

    def _send_request(self, payload: dict) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            return httpx.post(self.base_url, json=payload, headers=headers, timeout=60.0)
        except httpx.RequestError as exc:
            raise ProviderError(f"OpenRouter STT request failed: {exc}") from exc

    def _parse_response(self, response: httpx.Response) -> str:
        if response.status_code >= 400:
            try:
                body = response.json()
                error_msg = body.get("error", {}).get("message", response.text[:200])
            except Exception:
                error_msg = response.text[:200]
            raise ProviderResponseError(
                f"OpenRouter STT error (status {response.status_code}): {error_msg}"
            )

        try:
            body = response.json()
        except Exception as exc:
            raise ProviderResponseError(
                f"OpenRouter STT returned non-JSON response: {response.text[:200]}"
            ) from exc

        try:
            text = body["text"]
        except KeyError as exc:
            raise ProviderResponseError(
                f"Unexpected OpenRouter STT response structure: {str(body)[:200]}"
            ) from exc

        return finalize_whisper_text(text, self.post_process)
