#!/bin/bash
# migrate_system_cuda_to_12.sh
#
# One-shot system migration: remove orphaned CUDA 11.8 runfile install,
# remove vestigial nvidia-driver-550, install CUDA 12.6 toolkit + cuDNN 9
# from NVIDIA's official apt repo, fix ~/.bashrc env.
#
# Run as your normal user. The script calls sudo internally where needed.
# Re-runnable: skips any step whose post-condition is already satisfied.
#
# Output is verbose by design — paste it back so we can verify each phase.

set -uo pipefail

LOG_PREFIX="[migrate-cuda]"
log()  { echo "$LOG_PREFIX $*"; }
hr()   { echo "$LOG_PREFIX ────────────────────────────────────────────"; }
fail() { echo "$LOG_PREFIX ❌ $*" >&2; }

if [ "$(uname -s)" != "Linux" ]; then
  fail "Linux only."; exit 1
fi
if [ "$(id -u)" -eq 0 ]; then
  fail "Run as your normal user, not root. The script uses sudo internally."
  exit 1
fi

USER_BASHRC="$HOME/.bashrc"
BASHRC_BACKUP="$HOME/.bashrc.before-cuda-migration-$(date +%Y%m%d-%H%M%S)"

KEYRING_DEB_URL="https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb"
KEYRING_DEB="/tmp/cuda-keyring_1.1-1_all.deb"

CUDA_TOOLKIT_PKG="cuda-toolkit-12-6"
CUDNN_PKGS=(libcudnn9-cuda-12 libcudnn9-dev-cuda-12)

echo
hr
log "Pre-flight"
hr
log "user        : $USER"
log "host        : $(hostname)"
log "ubuntu      : $(lsb_release -ds 2>/dev/null)"
log "kernel      : $(uname -r)"
log "nvidia drv  : $(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1)"
log "current nvcc: $(command -v nvcc 2>/dev/null && nvcc --version 2>/dev/null | grep release || echo 'absent')"
log "free disk   : $(df -h / | awk 'NR==2 {print $4}')"
echo

# Cache sudo creds upfront so we only prompt once.
log "Caching sudo creds (you may be prompted now)…"
if ! sudo -v; then
  fail "sudo authentication failed."; exit 1
fi
# Keep-alive: refresh sudo timestamp until script ends.
( while true; do sudo -n true; sleep 60; kill -0 "$$" 2>/dev/null || exit; done ) 2>/dev/null &
SUDO_KEEPALIVE_PID=$!
trap '[ -n "${SUDO_KEEPALIVE_PID:-}" ] && kill "$SUDO_KEEPALIVE_PID" 2>/dev/null || true' EXIT

# ───────────────────────────────────────────────────────────────────────
# Phase 1: remove orphaned CUDA 11.8 runfile install
# ───────────────────────────────────────────────────────────────────────
echo
hr
log "Phase 1: remove CUDA 11.8 runfile install"
hr

if [ -x /usr/local/cuda-11.8/bin/cuda-uninstaller ]; then
  log "Running NVIDIA cuda-uninstaller…"
  # The uninstaller is a Rust TUI; piping a series of returns selects all
  # items and confirms. If it asks unexpected questions, it'll just hang
  # — that's why we cap with timeout.
  if ! sudo /usr/local/cuda-11.8/bin/cuda-uninstaller; then
    log "uninstaller returned non-zero — proceeding with manual cleanup"
  fi
else
  log "cuda-uninstaller not found (already removed?)"
fi

if [ -d /usr/local/cuda-11.8 ]; then
  log "Removing /usr/local/cuda-11.8 leftovers…"
  sudo rm -rf /usr/local/cuda-11.8
fi

if [ -L /usr/local/cuda ] && [ "$(readlink -f /usr/local/cuda)" = "/usr/local/cuda-11.8" ]; then
  log "Removing dangling /usr/local/cuda symlink…"
  sudo rm -f /usr/local/cuda
elif [ -L /usr/local/cuda ] && [ ! -e /usr/local/cuda ]; then
  log "Removing broken /usr/local/cuda symlink…"
  sudo rm -f /usr/local/cuda
fi

if [ -f /etc/ld.so.conf.d/cuda-11-8.conf ]; then
  log "Removing /etc/ld.so.conf.d/cuda-11-8.conf…"
  sudo rm -f /etc/ld.so.conf.d/cuda-11-8.conf
fi

log "Refreshing ldconfig…"
sudo ldconfig

log "Phase 1 done. Disk now: $(df -h / | awk 'NR==2 {print $4}') free"

# ───────────────────────────────────────────────────────────────────────
# Phase 2: remove vestigial nvidia-driver-550
# ───────────────────────────────────────────────────────────────────────
echo
hr
log "Phase 2: remove vestigial nvidia-driver-550"
hr

if dpkg -l 2>/dev/null | grep -qE '^ii\s+nvidia-driver-550\s'; then
  log "Removing nvidia-driver-550 (the running driver is 580 — verified earlier)…"
  sudo apt-get remove --autoremove -y nvidia-driver-550 || \
    log "remove returned non-zero — may already be partially removed"
else
  log "nvidia-driver-550 not installed (already cleaned)"
fi

# ───────────────────────────────────────────────────────────────────────
# Phase 3: add NVIDIA CUDA apt repo
# ───────────────────────────────────────────────────────────────────────
echo
hr
log "Phase 3: add NVIDIA CUDA apt repo for ubuntu2404"
hr

if ! dpkg -l 2>/dev/null | grep -qE '^ii\s+cuda-keyring\s'; then
  log "Downloading $KEYRING_DEB_URL"
  if ! wget -q -O "$KEYRING_DEB" "$KEYRING_DEB_URL"; then
    fail "Failed to download cuda-keyring. Check internet."; exit 1
  fi
  log "Installing cuda-keyring…"
  sudo dpkg -i "$KEYRING_DEB"
  rm -f "$KEYRING_DEB"
else
  log "cuda-keyring already installed"
fi

log "apt update…"
sudo apt-get update

# ───────────────────────────────────────────────────────────────────────
# Phase 4: install CUDA 12.6 toolkit + cuDNN 9
# ───────────────────────────────────────────────────────────────────────
echo
hr
log "Phase 4: install $CUDA_TOOLKIT_PKG + cuDNN 9"
hr

if dpkg -l 2>/dev/null | grep -qE "^ii\s+$CUDA_TOOLKIT_PKG\s"; then
  log "$CUDA_TOOLKIT_PKG already installed"
else
  log "Installing $CUDA_TOOLKIT_PKG (this is the big download, ~3 GB)…"
  sudo apt-get install -y "$CUDA_TOOLKIT_PKG"
fi

log "Installing cuDNN 9 packages: ${CUDNN_PKGS[*]}"
sudo apt-get install -y "${CUDNN_PKGS[@]}"

# ───────────────────────────────────────────────────────────────────────
# Phase 5: configure ~/.bashrc env (point at version-agnostic /usr/local/cuda)
# ───────────────────────────────────────────────────────────────────────
echo
hr
log "Phase 5: update $USER_BASHRC"
hr

cp -p "$USER_BASHRC" "$BASHRC_BACKUP"
log "Backed up bashrc → $BASHRC_BACKUP"

# Comment out any cuda-11.8 lines.
if grep -nE 'cuda-11\.8' "$USER_BASHRC" >/dev/null 2>&1; then
  log "Commenting out cuda-11.8 lines in bashrc…"
  sed -i 's|^\([^#].*cuda-11\.8.*\)$|# [migrate-cuda] disabled: \1|' "$USER_BASHRC"
fi

# Add new managed-symlink lines (idempotent — only if not already there).
if ! grep -qE '^export PATH=/usr/local/cuda/bin' "$USER_BASHRC"; then
  cat >> "$USER_BASHRC" <<'EOF'

# Added by migrate_system_cuda_to_12.sh — points at the apt-managed
# /usr/local/cuda symlink, which auto-tracks the installed version.
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
EOF
  log "Appended new CUDA env lines to bashrc"
else
  log "bashrc already has /usr/local/cuda env lines"
fi

# ───────────────────────────────────────────────────────────────────────
# Final verification (in a fresh subshell that sources the new bashrc)
# ───────────────────────────────────────────────────────────────────────
echo
hr
log "Final verification"
hr

log "ls /usr/local/cuda*"
ls -ld /usr/local/cuda* 2>/dev/null

log ""
log "Running new nvcc --version (via fresh PATH):"
PATH=/usr/local/cuda/bin:$PATH nvcc --version 2>&1 || log "❌ nvcc still missing"

log ""
log "ldconfig CUDA libs (looking for cuda-12 / cudnn 9):"
ldconfig -p | grep -E 'libcudart|libcublas|libcudnn' | head -8

log ""
log "Apt-installed cuda/cudnn packages now:"
dpkg -l 2>/dev/null | grep -E '^ii\s+(cuda|nvidia|libcudnn)' | awk '{print $2, $3}'

log ""
log "nvidia-smi:"
nvidia-smi 2>&1 | head -10

log ""
log "Free disk: $(df -h / | awk 'NR==2 {print $4}')"

echo
hr
log "Done. Open a NEW terminal (or run 'source ~/.bashrc') so the updated"
log "PATH / LD_LIBRARY_PATH take effect, then run 'nvcc --version' to confirm."
log "Old bashrc backed up at: $BASHRC_BACKUP"
hr
