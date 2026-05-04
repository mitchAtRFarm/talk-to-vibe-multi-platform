#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="TalkToVibe"
USER_BIN="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$DESKTOP_DIR/${APP_NAME}.desktop"
AUTOSTART_FILE="$AUTOSTART_DIR/${APP_NAME}.desktop"
LAUNCHER="$USER_BIN/talktovibe"

CONFIG_PATH="$HOME/.talktovibe/config.yaml"
LOG_DIR="$HOME/.talktovibe/logs"
APP_SUPPORT_DIR="$HOME/.talktovibe"
VENV_DIR="$SCRIPT_DIR/.venv"

AUTO_YES=0
KEEP_CONFIG=0
REMOVE_VENV=0

usage() {
  cat <<EOF
Usage: ./uninstall_linux.sh [options]

Options:
  --yes           Accept prompts with recommended defaults
  --keep-config   Preserve ~/.talktovibe/config.yaml
  --remove-venv   Also delete the local .venv directory inside the repo
EOF
}

confirm() {
  local prompt="$1"
  local default_answer="${2:-n}"
  if [ "$AUTO_YES" -eq 1 ]; then
    [ "$default_answer" = "y" ]
    return
  fi
  local suffix="[y/N]"
  if [ "$default_answer" = "y" ]; then
    suffix="[Y/n]"
  fi
  read -r -p "$prompt $suffix " reply
  reply="${reply:-$default_answer}"
  [[ "$reply" =~ ^[Yy]$ ]]
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --yes) AUTO_YES=1 ;;
      --keep-config) KEEP_CONFIG=1 ;;
      --remove-venv) REMOVE_VENV=1 ;;
      -h|--help) usage; exit 0 ;;
      *) echo "Unknown option: $1"; usage; exit 1 ;;
    esac
    shift
  done
}

stop_app() {
  pkill -f "talk_to_vibe" >/dev/null 2>&1 || true
  pkill -f "$LAUNCHER" >/dev/null 2>&1 || true
}

remove_files() {
  rm -f "$LAUNCHER"
  rm -f "$DESKTOP_FILE"
  rm -f "$AUTOSTART_FILE"
  rm -rf "$LOG_DIR"

  if [ "$KEEP_CONFIG" -eq 0 ]; then
    rm -f "$CONFIG_PATH"
    rmdir "$APP_SUPPORT_DIR" >/dev/null 2>&1 || true
  fi

  if [ "$REMOVE_VENV" -eq 1 ] && [ -d "$VENV_DIR" ]; then
    rm -rf "$VENV_DIR"
    echo "  Removed venv: $VENV_DIR"
  fi
}

main() {
  parse_args "$@"

  if [ "$AUTO_YES" -ne 1 ]; then
    if ! confirm "Remove TalkToVibe launcher, desktop entry, autostart, and logs?" "y"; then
      echo "Cancelled."
      exit 0
    fi
  fi

  stop_app
  remove_files

  echo "✅ TalkToVibe Linux uninstall complete"
  echo "  Removed launcher:      $LAUNCHER"
  echo "  Removed desktop entry: $DESKTOP_FILE"
  echo "  Removed autostart:     $AUTOSTART_FILE"
  if [ "$KEEP_CONFIG" -eq 1 ]; then
    echo "  Preserved config:      $CONFIG_PATH"
  fi
  echo ""
  echo "Note: system packages installed by setup_linux.sh (libportaudio2, xclip, etc.)"
  echo "are not removed. Use 'sudo apt-get remove <pkg>' if you want them gone."
}

main "$@"
