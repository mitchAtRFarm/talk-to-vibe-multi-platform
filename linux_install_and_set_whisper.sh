#!/bin/bash
# linux_install_and_set_whisper.sh
#
# Detect compatibility, install faster-whisper + the large-v3-turbo model
# into the TalkToVibe venv, and reconfigure ~/.talktovibe/config.yaml so
# the app uses the local_whisper provider.
#
# This script intentionally does NOT modify the system CUDA toolkit. It
# uses pip wheels (nvidia-cublas-cu12, nvidia-cudnn-cu12) that ship the
# matching cuBLAS/cuDNN libs inside the venv. That sidesteps system CUDA
# version mismatches (e.g. nvcc 11.8 vs driver supporting CUDA 13) without
# touching anything outside the project.
#
# Usage: ./linux_install_and_set_whisper.sh [options]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"
REQ_LOCAL="$SCRIPT_DIR/requirements-local-whisper.txt"
SMOKE_TEST="$SCRIPT_DIR/tools/local_whisper_smoke_test.py"
CONFIG_FILE="$HOME/.talktovibe/config.yaml"

MODEL_SIZE="large-v3-turbo"
LANGUAGE="en"
DEVICE="auto"
COMPUTE_TYPE="auto"
AUTO_YES=0
FORCE_CPU=0
SKIP_SMOKE=0
SKIP_CONFIG=0
DRY_RUN=0
MIN_DISK_GB=8
MIN_RAM_GB=4
MIN_VRAM_MB=2500

color_red() { printf '\033[31m%s\033[0m' "$1"; }
color_yellow() { printf '\033[33m%s\033[0m' "$1"; }
color_green() { printf '\033[32m%s\033[0m' "$1"; }
color_cyan() { printf '\033[36m%s\033[0m' "$1"; }

info()  { echo "$(color_cyan "ℹ ") $*"; }
ok()    { echo "$(color_green "✅") $*"; }
warn()  { echo "$(color_yellow "⚠ ") $*"; }
fail()  { echo "$(color_red "❌") $*" >&2; }

usage() {
  cat <<EOF
Usage: ./linux_install_and_set_whisper.sh [options]

Options:
  --model SIZE         Model to install (default: $MODEL_SIZE).
                       Examples: tiny, base, small, medium, large-v3,
                                 large-v3-turbo, distil-large-v3
  --language LANG      Whisper language hint (default: $LANGUAGE; 'auto' to autodetect)
  --device DEV         auto | cuda | cpu (default: auto)
  --compute-type CT    auto | float16 | int8_float16 | int8 | float32 (default: auto)
  --cpu                Force CPU install (skip nvidia-* wheels even if GPU present)
  --skip-smoke         Skip the post-install transcription smoke test
  --skip-config        Don't write config.yaml (install + test only)
  --yes                Don't prompt — accept defaults
  --dry-run            Print actions and exit
  -h, --help           Show this help

What it does:
  1. Inspect the machine (Python, disk, GPU, CUDA driver, RAM, ffmpeg).
  2. Decide CPU-only vs CUDA path.
  3. Create/reuse .venv, install faster-whisper + bundled CUDA wheels.
  4. Pre-download the chosen Whisper model into the HF cache.
  5. Run a smoke test that loads the model and transcribes synthetic audio,
     reporting realtime factor and which device was used.
  6. Update ~/.talktovibe/config.yaml so provider = local_whisper.
EOF
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --model) MODEL_SIZE="$2"; shift ;;
      --language) LANGUAGE="$2"; shift ;;
      --device) DEVICE="$2"; shift ;;
      --compute-type) COMPUTE_TYPE="$2"; shift ;;
      --cpu) FORCE_CPU=1 ;;
      --skip-smoke) SKIP_SMOKE=1 ;;
      --skip-config) SKIP_CONFIG=1 ;;
      --yes) AUTO_YES=1 ;;
      --dry-run) DRY_RUN=1 ;;
      -h|--help) usage; exit 0 ;;
      *) fail "Unknown option: $1"; usage; exit 1 ;;
    esac
    shift
  done
}

confirm() {
  local prompt="$1"
  local default="${2:-y}"
  if [ "$AUTO_YES" -eq 1 ]; then
    [ "$default" = "y" ]
    return
  fi
  local suffix="[y/N]"
  [ "$default" = "y" ] && suffix="[Y/n]"
  read -r -p "$prompt $suffix " reply
  reply="${reply:-$default}"
  [[ "$reply" =~ ^[Yy]$ ]]
}

require_linux() {
  if [ "$(uname -s)" != "Linux" ]; then
    fail "linux_install_and_set_whisper.sh only supports Linux."
    exit 1
  fi
}

# ---- detection ----

PY_VERSION=""
PY_OK=0
DISK_FREE_GB=0
DISK_OK=0
RAM_TOTAL_GB=0
RAM_OK=0
HAS_NVIDIA_DRIVER=0
NVIDIA_DRIVER_VERSION=""
NVIDIA_GPU_NAME=""
NVIDIA_VRAM_MB=0
NVIDIA_CUDA_DRIVER_API=""
HAS_NVCC=0
NVCC_VERSION=""
HAS_FFMPEG=0
WANT_GPU=0
HAS_AVX2=0

detect_python() {
  if ! command -v python3 >/dev/null 2>&1; then
    fail "python3 is required and not found on PATH."
    exit 1
  fi
  PY_VERSION="$(python3 -c 'import sys; print("%d.%d"%sys.version_info[:2])')"
  local major minor
  IFS='.' read -r major minor <<< "$PY_VERSION"
  if [ "$major" -lt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -lt 9 ]; }; then
    PY_OK=0
  else
    PY_OK=1
  fi
}

detect_disk() {
  local kb
  kb="$(df -P "$HOME" | awk 'NR==2 {print $4}')"
  DISK_FREE_GB="$(( kb / 1024 / 1024 ))"
  if [ "$DISK_FREE_GB" -ge "$MIN_DISK_GB" ]; then DISK_OK=1; else DISK_OK=0; fi
}

detect_ram() {
  local kb
  kb="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)"
  RAM_TOTAL_GB="$(( kb / 1024 / 1024 ))"
  if [ "$RAM_TOTAL_GB" -ge "$MIN_RAM_GB" ]; then RAM_OK=1; else RAM_OK=0; fi
}

detect_avx2() {
  if grep -q -m1 'avx2' /proc/cpuinfo; then HAS_AVX2=1; else HAS_AVX2=0; fi
}

detect_nvidia() {
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    HAS_NVIDIA_DRIVER=0
    return
  fi
  HAS_NVIDIA_DRIVER=1
  NVIDIA_DRIVER_VERSION="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1 | tr -d ' ')"
  NVIDIA_GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 | sed 's/^ *//')"
  NVIDIA_VRAM_MB="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')"
  NVIDIA_CUDA_DRIVER_API="$(nvidia-smi 2>/dev/null | grep -oE 'CUDA Version: [0-9.]+' | head -1 | awk '{print $3}')"
}

detect_nvcc() {
  if command -v nvcc >/dev/null 2>&1; then
    HAS_NVCC=1
    NVCC_VERSION="$(nvcc --version | grep -oE 'release [0-9.]+' | awk '{print $2}')"
  fi
}

detect_ffmpeg() {
  command -v ffmpeg >/dev/null 2>&1 && HAS_FFMPEG=1 || HAS_FFMPEG=0
}

run_detection() {
  info "Inspecting system…"
  detect_python
  detect_disk
  detect_ram
  detect_avx2
  detect_nvidia
  detect_nvcc
  detect_ffmpeg
}

print_report() {
  echo
  echo "──────────── Compatibility report ────────────"
  printf "  %-22s " "python3:"
  if [ "$PY_OK" -eq 1 ]; then ok "$PY_VERSION (>= 3.9 required)"; else fail "$PY_VERSION (need >= 3.9)"; fi
  printf "  %-22s " "free disk on \$HOME:"
  if [ "$DISK_OK" -eq 1 ]; then ok "${DISK_FREE_GB} GB"; else warn "${DISK_FREE_GB} GB (recommended >= ${MIN_DISK_GB} GB)"; fi
  printf "  %-22s " "system RAM:"
  if [ "$RAM_OK" -eq 1 ]; then ok "${RAM_TOTAL_GB} GB"; else warn "${RAM_TOTAL_GB} GB (recommended >= ${MIN_RAM_GB} GB)"; fi
  printf "  %-22s " "CPU AVX2 support:"
  if [ "$HAS_AVX2" -eq 1 ]; then ok "yes"; else warn "no (CPU inference will be slow)"; fi
  printf "  %-22s " "ffmpeg:"
  if [ "$HAS_FFMPEG" -eq 1 ]; then ok "found"; else info "not found (not required — we feed numpy directly)"; fi
  printf "  %-22s " "NVIDIA driver:"
  if [ "$HAS_NVIDIA_DRIVER" -eq 1 ]; then
    ok "$NVIDIA_GPU_NAME, driver $NVIDIA_DRIVER_VERSION (CUDA driver API $NVIDIA_CUDA_DRIVER_API), ${NVIDIA_VRAM_MB} MB VRAM"
  else
    info "no nvidia-smi — CPU-only path"
  fi
  printf "  %-22s " "system nvcc:"
  if [ "$HAS_NVCC" -eq 1 ]; then
    info "$NVCC_VERSION (informational only — we use pip-bundled CUDA libs)"
  else
    info "not installed (not required)"
  fi
  echo "───────────────────────────────────────────────"
  echo
}

decide_gpu_path() {
  if [ "$FORCE_CPU" -eq 1 ]; then
    WANT_GPU=0
    info "GPU path disabled (--cpu)."
    return
  fi
  if [ "$HAS_NVIDIA_DRIVER" -eq 0 ]; then
    WANT_GPU=0
    info "No NVIDIA GPU detected — installing CPU-only build."
    return
  fi
  if [ "$NVIDIA_VRAM_MB" -lt "$MIN_VRAM_MB" ]; then
    warn "GPU has ${NVIDIA_VRAM_MB} MB VRAM, recommend >= ${MIN_VRAM_MB} MB for ${MODEL_SIZE}."
    if confirm "Install GPU build anyway?" "y"; then
      WANT_GPU=1
    else
      WANT_GPU=0
    fi
    return
  fi
  WANT_GPU=1
  ok "Will install GPU-accelerated build (using bundled CUDA 12 wheels)."
}

print_plan() {
  echo "Plan:"
  echo "  - venv:           $VENV_DIR  (create if missing, with --system-site-packages)"
  echo "  - core deps:      requirements.txt"
  echo "  - whisper deps:   $REQ_LOCAL"
  if [ "$WANT_GPU" -eq 1 ]; then
    echo "  - cuda libs:      pip wheels (nvidia-cublas-cu12, nvidia-cudnn-cu12)"
    echo "  - device:         cuda (auto-resolved at runtime)"
  else
    echo "  - device:         cpu"
  fi
  echo "  - model:          $MODEL_SIZE (downloaded from Hugging Face on first load)"
  echo "  - smoke test:     $([ "$SKIP_SMOKE" -eq 1 ] && echo "skipped" || echo "yes")"
  echo "  - config update:  $([ "$SKIP_CONFIG" -eq 1 ] && echo "skipped" || echo "yes  ($CONFIG_FILE)")"
  echo
}

# ---- install ----

ensure_venv() {
  if [ ! -d "$VENV_DIR" ]; then
    info "Creating venv at $VENV_DIR (with --system-site-packages)…"
    python3 -m venv --system-site-packages "$VENV_DIR"
  else
    info "Reusing existing venv at $VENV_DIR"
  fi
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  python -m pip install --upgrade pip >/dev/null
}

install_core_requirements() {
  info "Installing core TalkToVibe requirements…"
  pip install -q -r "$SCRIPT_DIR/requirements.txt"
}

install_whisper_requirements() {
  info "Installing faster-whisper deps…"
  if [ "$WANT_GPU" -eq 1 ]; then
    pip install -q -r "$REQ_LOCAL"
  else
    # CPU-only: skip the heavy nvidia-* wheels
    pip install -q "faster-whisper>=1.1.0" "ctranslate2>=4.5.0"
  fi
}

prefetch_model() {
  info "Pre-downloading model '$MODEL_SIZE' (this is a one-time download, can be ~1.5–3 GB)…"
  python - <<PY
import sys
from faster_whisper import download_model
try:
    path = download_model("${MODEL_SIZE}")
    print(f"  cached at: {path}")
except Exception as exc:
    print(f"  ❌ download failed: {type(exc).__name__}: {exc}", file=sys.stderr)
    sys.exit(1)
PY
}

run_smoke_test() {
  info "Running smoke test…"
  local require_flag=""
  if [ "$WANT_GPU" -eq 1 ]; then
    require_flag="--require-gpu"
  fi
  PYTHONPATH="$SCRIPT_DIR" python "$SMOKE_TEST" \
    --model-size "$MODEL_SIZE" \
    --device "$DEVICE" \
    --compute-type "$COMPUTE_TYPE" \
    $require_flag
}

write_config() {
  info "Updating $CONFIG_FILE → provider = local_whisper"
  PYTHONPATH="$SCRIPT_DIR" python - <<PY
from talk_to_vibe.config.constants import CONFIG_FILE
from talk_to_vibe.config.loader import load_config, save_config

config = load_config()
config.provider = "local_whisper"
config.providers.local_whisper.model_size = "${MODEL_SIZE}"
config.providers.local_whisper.device = "${DEVICE}"
config.providers.local_whisper.compute_type = "${COMPUTE_TYPE}"
config.providers.local_whisper.language = "${LANGUAGE}"
save_config(config)
print(f"  wrote {CONFIG_FILE}")
PY
}

print_post_install() {
  echo
  ok "Local Whisper installed."
  echo
  echo "  To launch TalkToVibe:    $SCRIPT_DIR/run_ttv.sh"
  echo "  Re-run smoke test:       $VENV_DIR/bin/python $SMOKE_TEST"
  echo "  Switch back to cloud:    edit $CONFIG_FILE → provider: groq (or run --setup)"
  echo
  if [ "$WANT_GPU" -eq 1 ]; then
    echo "  CUDA libs are pip-bundled inside $VENV_DIR — no system CUDA changes were made."
    echo "  System nvcc ($NVCC_VERSION) is unchanged and not used by faster-whisper."
  fi
}

main() {
  parse_args "$@"
  require_linux
  run_detection
  print_report

  if [ "$PY_OK" -eq 0 ]; then
    fail "Python 3.9+ is required."
    exit 1
  fi
  if [ "$DISK_OK" -eq 0 ]; then
    if ! confirm "Disk space is low. Continue?" "n"; then exit 1; fi
  fi

  decide_gpu_path
  print_plan

  if [ "$DRY_RUN" -eq 1 ]; then
    info "--dry-run: not installing anything."
    exit 0
  fi

  if ! confirm "Proceed with install?" "y"; then
    info "Aborted."
    exit 0
  fi

  ensure_venv
  install_core_requirements
  install_whisper_requirements
  prefetch_model

  if [ "$SKIP_SMOKE" -eq 0 ]; then
    if ! run_smoke_test; then
      fail "Smoke test failed. Config will NOT be updated."
      exit 1
    fi
  fi

  if [ "$SKIP_CONFIG" -eq 0 ]; then
    write_config
  fi

  print_post_install
}

main "$@"
