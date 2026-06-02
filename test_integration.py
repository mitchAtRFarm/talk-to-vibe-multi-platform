#!/usr/bin/env python3
"""Integration test: Verify openai_compatible provider works against live server."""

import numpy as np
import sys
import traceback

from talk_to_vibe.config.loader import load_config
from talk_to_vibe.providers.factory import create_provider


def generate_test_audio(duration_sec=1.0, sample_rate=16000):
    """Generate silent audio for testing."""
    samples = int(duration_sec * sample_rate)
    return np.zeros((samples, 1), dtype=np.int16)


def main():
    print("=" * 60)
    print("TalkToVibe Provider Integration Test")
    print("=" * 60)

    # Step 1: Load config
    print("\n[1/4] Loading config from ~/.talktovibe/config.yaml...")
    try:
        config = load_config()
        print(f"  Provider: {config.provider}")
        print(f"  PTT Key: {config.ptt_key}")
        compat = config.providers.openai_compatible
        print(f"  Base URL: {compat.base_url}")
        print(f"  Model: {compat.model}")
        print(f"  Language: {compat.language or '(auto-detect)'}")
        print(f"  Post-process: {compat.post_process}")
        print(f"  Temperature: {compat.temperature}")
        print(f"  Hints file: {compat.hints_file or '(bundled)'}")
    except Exception as e:
        print(f"  ERROR: Failed to load config: {e}")
        traceback.print_exc()
        return 1

    # Step 2: Validate config
    print("\n[2/4] Validating config...")
    errors = config.validate()
    if errors:
        for err in errors:
            print(f"  ERROR: {err}")
        return 1
    print("  Config is valid.")

    # Step 3: Create provider
    print("\n[3/4] Creating provider via factory...")
    try:
        provider = create_provider(config)
        print(f"  Provider name: {provider.provider_name}")
        print(f"  Model: {provider.model}")
        print(f"  Language: {provider.language or '(auto-detect)'}")
        print(f"  Post-process: {provider.post_process}")
        print(f"  Temperature: {provider.temperature}")
        print(f"  Hints loaded: {len(provider.hints)} chars")
    except Exception as e:
        print(f"  ERROR: Failed to create provider: {e}")
        traceback.print_exc()
        return 1

    # Step 4: Send test audio
    print("\n[4/4] Sending test audio to server...")
    print("  Generating 1 second of silent audio...")
    audio = generate_test_audio()
    print(f"  Audio shape: {audio.shape}, dtype: {audio.dtype}")

    try:
        print("  Calling transcribe()...")
        text = provider.transcribe(audio)
        print(f"  SUCCESS! Transcription: '{text}'")
        print("\n" + "=" * 60)
        print("INTEGRATION TEST PASSED")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"  ERROR: Transcription failed: {e}")
        traceback.print_exc()
        print("\n" + "=" * 60)
        print("INTEGRATION TEST FAILED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())