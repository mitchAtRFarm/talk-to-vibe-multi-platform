"""Smoke test for the local Whisper install.

Loads the configured Whisper model, runs a short transcription against a
synthetic audio buffer, and prints diagnostic info: device used, compute
type, model size, real-time factor, and whether the bundled CUDA wheels
were preloaded.

Exit codes:
  0 — model loaded and transcribe() returned without raising
  2 — couldn't import faster-whisper (install incomplete)
  3 — model failed to load (likely CUDA library issue)
  4 — requested CUDA but fell back to CPU when --require-gpu was set
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time

import numpy as np


def _print_header(title: str) -> None:
    print(f"\n=== {title} ===")


def _gen_synth_audio(seconds: float, sample_rate: int = 16000) -> np.ndarray:
    """Generate ~speech-shaped audio: two formants modulated by an envelope.

    This isn't real speech — we don't care what the model transcribes, only
    that the pipeline runs end-to-end without crashing and that the GPU is
    used when expected.
    """
    n = int(seconds * sample_rate)
    t = np.linspace(0.0, seconds, n, endpoint=False, dtype=np.float32)
    f1 = 220.0 + 40.0 * np.sin(2 * np.pi * 2.0 * t)
    f2 = 880.0 + 120.0 * np.sin(2 * np.pi * 3.5 * t)
    sig = 0.4 * np.sin(2 * np.pi * f1 * t) + 0.2 * np.sin(2 * np.pi * f2 * t)
    env = 0.5 * (1 + np.sin(2 * np.pi * 1.5 * t))
    sig = sig * env
    # Convert to int16 to match the recorder's output dtype.
    return (sig * 0.5 * 32767).astype(np.int16)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-size", default=None, help="Override model_size")
    parser.add_argument("--device", default=None, help="Override device (auto/cuda/cpu)")
    parser.add_argument("--compute-type", default=None, help="Override compute_type")
    parser.add_argument("--require-gpu", action="store_true", help="Fail if not running on CUDA")
    parser.add_argument("--seconds", type=float, default=2.0, help="Synthetic audio length")
    parser.add_argument("--json", action="store_true", help="Emit a single JSON result line")
    args = parser.parse_args()

    _print_header("Environment")
    print(f"python  : {platform.python_version()}")
    print(f"system  : {platform.system()} {platform.release()}")
    print(f"machine : {platform.machine()}")

    _print_header("Loading config")
    from talk_to_vibe.config.loader import load_config

    config = load_config()
    lw = config.providers.local_whisper
    model_size = args.model_size or lw.model_size
    device = args.device or lw.device
    compute_type = args.compute_type or lw.compute_type
    print(f"model_size   : {model_size}")
    print(f"device (req) : {device}")
    print(f"compute_type : {compute_type}")
    print(f"language     : {lw.language}")

    _print_header("Preloading bundled CUDA libs")
    try:
        from talk_to_vibe.providers.local_whisper import _preload_bundled_cuda_libs
    except Exception as exc:
        print(f"❌ couldn't import provider module: {exc}")
        return 2
    preloaded, msg = _preload_bundled_cuda_libs()
    print(f"preloaded={preloaded} ({msg})")

    _print_header("Importing faster-whisper")
    try:
        import faster_whisper
    except ImportError as exc:
        print(f"❌ faster-whisper not installed: {exc}")
        return 2
    print(f"faster-whisper version: {getattr(faster_whisper, '__version__', 'unknown')}")

    _print_header("Loading model")
    from talk_to_vibe.providers.local_whisper import LocalWhisperProvider

    try:
        t0 = time.time()
        provider = LocalWhisperProvider(
            model_size=model_size,
            device=device,
            compute_type=compute_type,
            language=lw.language,
            model_dir=lw.model_dir,
            cpu_threads=lw.cpu_threads,
            beam_size=lw.beam_size,
            vad_filter=lw.vad_filter,
        )
        load_secs = time.time() - t0
    except Exception as exc:
        print(f"❌ failed to load model: {type(exc).__name__}: {exc}")
        return 3

    print(f"resolved device      : {provider.device}")
    print(f"resolved compute     : {provider.compute_type}")
    print(f"model load time (s)  : {load_secs:.2f}")

    if args.require_gpu and provider.device != "cuda":
        print("❌ --require-gpu set but model loaded on CPU")
        return 4

    _print_header("Running transcribe()")
    audio = _gen_synth_audio(args.seconds)
    t0 = time.time()
    text = provider.transcribe(audio)
    transcribe_secs = time.time() - t0
    rtf = transcribe_secs / args.seconds if args.seconds > 0 else float("nan")
    print(f"audio length (s)     : {args.seconds}")
    print(f"transcribe time (s)  : {transcribe_secs:.3f}")
    print(f"realtime factor      : {rtf:.3f}x  (lower is faster — <0.1 means >10x realtime)")
    snippet = text[:120].replace("\n", " ")
    print(f"text (first 120ch)   : {snippet!r}")

    if provider.device == "cuda":
        try:
            import subprocess
            out = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-compute-apps=pid,used_memory",
                    "--format=csv,noheader,nounits",
                ],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            mine = [line for line in out.splitlines() if line.strip().startswith(str(os.getpid()))]
            print(f"VRAM (this PID)      : {mine or 'no entry yet'}")
        except (FileNotFoundError, subprocess.SubprocessError):
            pass

    if args.json:
        print()
        print(
            json.dumps(
                {
                    "ok": True,
                    "device": provider.device,
                    "compute_type": provider.compute_type,
                    "model_size": model_size,
                    "load_secs": load_secs,
                    "transcribe_secs": transcribe_secs,
                    "rtf": rtf,
                    "preloaded_cuda": preloaded,
                }
            )
        )

    print("\n✅ smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
