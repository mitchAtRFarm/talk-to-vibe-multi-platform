from talk_to_vibe.providers.base import BaseSTTProvider
from talk_to_vibe.providers.openai_whisper import OpenAIWhisperProvider
from talk_to_vibe.providers.openai_compatible import OpenAICompatibleProvider
from talk_to_vibe.providers.openrouter_multimodal import OpenRouterMultimodalProvider
from talk_to_vibe.providers.openrouter_whisper import OpenRouterWhisperProvider
from talk_to_vibe.providers.local_whisper import LocalWhisperProvider
from talk_to_vibe.config.models import AppConfig
from talk_to_vibe.errors import ProviderError, ProviderAuthError


def _setup_hint() -> str:
    return "Re-run setup or use the installed TalkToVibe app's Reconfigure menu item."


PROVIDER_REGISTRY = {
    "openrouter_whisper": OpenRouterWhisperProvider,
    "openai": OpenAIWhisperProvider,
    "openai_compatible": OpenAICompatibleProvider,
    "openrouter": OpenRouterMultimodalProvider,
    "local_whisper": LocalWhisperProvider,
}


def create_provider(config: AppConfig) -> BaseSTTProvider:
    provider_name = config.provider
    cls = PROVIDER_REGISTRY.get(provider_name)
    if cls is None:
        raise ProviderError(f"Unknown provider: {provider_name}")

    if provider_name == "local_whisper":
        lw = config.providers.local_whisper
        try:
            return cls(
                model_size=lw.model_size,
                device=lw.device,
                compute_type=lw.compute_type,
                language=lw.language,
                model_dir=lw.model_dir,
                cpu_threads=lw.cpu_threads,
                beam_size=lw.beam_size,
                vad_filter=lw.vad_filter,
                hints_file=lw.hints_file,
                post_process=lw.post_process,
            )
        except ImportError as exc:
            raise ProviderError(
                "faster-whisper is not installed. Run linux_install_and_set_whisper.sh "
                "to install it, or pip install faster-whisper inside the venv."
            ) from exc

    if provider_name == "openrouter_whisper":
        orw = config.providers.openrouter_whisper
        if not orw.api_key:
            raise ProviderAuthError(f"OpenRouter API key not found. {_setup_hint()}")
        return cls(
            api_key=orw.api_key,
            model=orw.model,
            base_url=orw.base_url,
            language=orw.language,
            hints_file=orw.hints_file,
            post_process=orw.post_process,
            temperature=orw.temperature,
            hint_provider_slug=orw.hint_provider_slug,
        )

    elif provider_name == "openai":
        if not config.providers.openai.api_key:
            raise ProviderAuthError(f"OpenAI API key not found. {_setup_hint()}")
        return cls(api_key=config.providers.openai.api_key, model=config.providers.openai.model)

    elif provider_name == "openai_compatible":
        if not config.providers.openai_compatible.base_url:
            raise ProviderAuthError(f"Base URL not found. {_setup_hint()}")
        return cls(
            base_url=config.providers.openai_compatible.base_url,
            api_key=config.providers.openai_compatible.api_key,
            model=config.providers.openai_compatible.model,
        )

    elif provider_name == "openrouter":
        if not config.providers.openrouter.api_key:
            raise ProviderAuthError(f"OpenRouter API key not found. {_setup_hint()}")
        return cls(
            api_key=config.providers.openrouter.api_key,
            model=config.providers.openrouter.model,
            base_url=config.providers.openrouter.base_url,
            prompt_file=config.prompt_file,
            service_tier=config.providers.openrouter.service_tier,
        )

    raise ProviderError(f"Unhandled provider: {provider_name}")
