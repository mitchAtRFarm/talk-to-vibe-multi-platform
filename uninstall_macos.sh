#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
VENV_DIR="$SCRIPT_DIR/.venv"
APP_DEST="$HOME/Applications/TalkToVibe.app"
HELPER_DEST="$HOME/.talktovibe/bin/talktovibe-configure"
MANIFEST_PATH="$HOME/.talktovibe/install-manifest.yaml"
LAUNCH_AGENT_PATH="$HOME/Library/LaunchAgents/com.talktovibe.app.plist"
CONFIG_PATH="$HOME/.talktovibe/config.yaml"
LOG_DIR="$HOME/.talktovibe/logs"
APP_SUPPORT_DIR="$HOME/.talktovibe"
SIGNING_DIR="$HOME/.talktovibe/signing"
SIGNING_KEYCHAIN="$SIGNING_DIR/talktovibe-signing.keychain-db"
AUTO_YES=0
KEEP_CONFIG=0
REMOVE_BREW_DEPS=0

usage() {
  cat <<EOF
Usage: ./uninstall_macos.sh [options]

Options:
  --yes               Accept prompts with recommended defaults
  --keep-config       Preserve ~/.talktovibe/config.yaml
  --remove-brew-deps  Prompt-free removal of Homebrew deps recorded by install
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

parse_manifest_brew_packages() {
  if ! load_manifest_field brew_packages >/dev/null 2>&1; then
    return 0
  fi
  load_manifest_field brew_packages || true
}

fallback_manifest_field() {
  local field="$1"
  if [ ! -f "$MANIFEST_PATH" ]; then
    return 1
  fi
  case "$field" in
    app_path|helper_path|launch_agent_path|bundle_identifier|install_version)
      awk -F': ' -v target="$field" '$1 == target {gsub(/^"|"$/, "", $2); print $2}' "$MANIFEST_PATH"
      ;;
    launch_at_login)
      awk -F': ' '$1 == "launch_at_login" {print $2}' "$MANIFEST_PATH"
      ;;
    brew_packages)
      awk '/^brew_packages:/ {sub(/^brew_packages: /, ""); print}' "$MANIFEST_PATH" | tr -d '[]"' | tr ',' '\n' | sed 's/^ *//;s/ *$//' | sed '/^$/d'
      ;;
    *)
      return 1
      ;;
  esac
}

load_manifest_field() {
  local field="$1"
  if [ ! -f "$MANIFEST_PATH" ]; then
    return 1
  fi
  if [ -x "$VENV_DIR/bin/python" ]; then
    if PYTHONPATH="$SCRIPT_DIR" "$VENV_DIR/bin/python" -m talk_to_vibe.install.macos_cli print-manifest-field --path "$MANIFEST_PATH" --field "$field"; then
      return 0
    fi
  fi
  fallback_manifest_field "$field"
}

load_manifest_paths() {
  local value
  if value="$(load_manifest_field app_path 2>/dev/null)" && [ -n "$value" ]; then
    APP_DEST="$value"
  fi
  if value="$(load_manifest_field helper_path 2>/dev/null)" && [ -n "$value" ]; then
    HELPER_DEST="$value"
  fi
  if value="$(load_manifest_field launch_agent_path 2>/dev/null)" && [ -n "$value" ]; then
    LAUNCH_AGENT_PATH="$value"
  fi
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --yes)
        AUTO_YES=1
        ;;
      --keep-config)
        KEEP_CONFIG=1
        ;;
      --remove-brew-deps)
        REMOVE_BREW_DEPS=1
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "Unknown option: $1"
        usage
        exit 1
        ;;
    esac
    shift
  done
}

stop_app() {
  osascript -e 'tell application "TalkToVibe" to quit' >/dev/null 2>&1 || true
  pkill -f "$APP_DEST" >/dev/null 2>&1 || true
}

remove_launch_agent() {
  if [ -f "$LAUNCH_AGENT_PATH" ]; then
    launchctl unload "$LAUNCH_AGENT_PATH" >/dev/null 2>&1 || true
    rm -f "$LAUNCH_AGENT_PATH"
  fi
}

remove_signing_keychain_from_search_list() {
  if [ ! -f "$SIGNING_KEYCHAIN" ]; then
    return
  fi

  local existing_keychains filtered_keychains keychain
  existing_keychains="$(security list-keychains -d user | tr -d '"')"
  filtered_keychains=""
  while IFS= read -r keychain; do
    [ -n "$keychain" ] || continue
    if [ "$keychain" != "$SIGNING_KEYCHAIN" ]; then
      filtered_keychains="$filtered_keychains $keychain"
    fi
  done <<< "$existing_keychains"

  if [ -n "$filtered_keychains" ]; then
    security list-keychains -d user -s $filtered_keychains >/dev/null
  fi
}

remove_files() {
  rm -rf "$APP_DEST"
  rm -f "$HELPER_DEST"
  rm -rf "$LOG_DIR"
   rm -rf "$SIGNING_DIR"

  if [ "$KEEP_CONFIG" -eq 0 ]; then
    rm -f "$CONFIG_PATH"
  fi

  rm -f "$MANIFEST_PATH"
  rmdir "$APP_SUPPORT_DIR/bin" >/dev/null 2>&1 || true
  rmdir "$APP_SUPPORT_DIR" >/dev/null 2>&1 || true
}

remove_brew_deps() {
  if [ "$REMOVE_BREW_DEPS" -ne 1 ]; then
    return
  fi

  local packages
  packages="$(parse_manifest_brew_packages || true)"
  if [ -z "$packages" ]; then
    return
  fi

  while IFS= read -r package; do
    [ -n "$package" ] || continue
    if brew list "$package" >/dev/null 2>&1; then
      brew uninstall "$package"
    fi
  done <<< "$packages"
}

main() {
  parse_args "$@"
  load_manifest_paths

  if [ "$AUTO_YES" -ne 1 ]; then
    if ! confirm "Remove TalkToVibe.app and its installed support files?" "y"; then
      echo "Cancelled."
      exit 0
    fi
  fi

  stop_app
  remove_launch_agent
  remove_signing_keychain_from_search_list
  remove_brew_deps
  remove_files

  echo "✅ TalkToVibe macOS uninstall complete"
  if [ "$KEEP_CONFIG" -eq 1 ]; then
    echo "  Preserved config: $CONFIG_PATH"
  fi
}

main "$@"
