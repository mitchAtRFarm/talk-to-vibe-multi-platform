#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"
APP_NAME="TalkToVibe"
USER_BIN="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$DESKTOP_DIR/${APP_NAME}.desktop"
AUTOSTART_FILE="$AUTOSTART_DIR/${APP_NAME}.desktop"
LAUNCHER="$USER_BIN/talktovibe"

AUTO_YES=0
SKIP_AUTOSTART=0
ENABLE_AUTOSTART=0
NO_LAUNCH=0
SKIP_APT=0
REUSE_CONFIG=0

APT_PACKAGES=(
  libportaudio2
  xclip
  xdotool
  libayatana-appindicator3-1
  gir1.2-ayatanaappindicator3-0.1
  python3-gi
  python3-gi-cairo
  libcanberra-gtk3-module
  libnotify-bin
  python3-venv
)

usage() {
  cat <<EOF
Usage: ./setup_linux.sh [options]

Options:
  --yes              Accept prompts with recommended defaults
  --no-launch        Do not launch TalkToVibe after installation
  --skip-autostart   Do not prompt for launch at login
  --enable-autostart Enable launch at login without prompting
  --skip-apt         Skip the apt-get install step (use if deps already met)
  --reuse-config     Skip the wizard if a valid ~/.talktovibe/config.yaml exists
  -h, --help         Show this help
EOF
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --yes) AUTO_YES=1 ;;
      --no-launch) NO_LAUNCH=1 ;;
      --skip-autostart) SKIP_AUTOSTART=1 ;;
      --enable-autostart) ENABLE_AUTOSTART=1 ;;
      --skip-apt) SKIP_APT=1 ;;
      --reuse-config) REUSE_CONFIG=1 ;;
      -h|--help) usage; exit 0 ;;
      *) echo "Unknown option: $1"; usage; exit 1 ;;
    esac
    shift
  done
}

confirm() {
  local prompt="$1"
  local default_answer="${2:-y}"
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

ensure_linux() {
  if [ "$(uname -s)" != "Linux" ]; then
    echo "❌ setup_linux.sh only supports Linux."
    exit 1
  fi
}

ensure_x11() {
  local session_type="${XDG_SESSION_TYPE:-}"
  if [ -n "${WAYLAND_DISPLAY:-}" ] || [ "$session_type" = "wayland" ]; then
    echo "⚠️  Wayland session detected (XDG_SESSION_TYPE=$session_type, WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-})."
    echo "   Global hotkey capture via pynput requires X11."
    echo "   Log out and pick a Cinnamon (X11) session at the login screen, then re-run this script."
    if ! confirm "Continue with installation anyway?" "n"; then
      exit 1
    fi
  fi
}

ensure_python3() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ python3 is required."
    exit 1
  fi
}

install_apt_deps() {
  if [ "$SKIP_APT" -eq 1 ]; then
    echo "  Skipping apt install (per --skip-apt)"
    return
  fi
  if ! command -v apt-get >/dev/null 2>&1; then
    echo "  apt-get not found — skipping system dependency install."
    echo "  Make sure these are present: ${APT_PACKAGES[*]}"
    return
  fi
  local missing=()
  for pkg in "${APT_PACKAGES[@]}"; do
    if ! dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed"; then
      missing+=("$pkg")
    fi
  done
  if [ "${#missing[@]}" -eq 0 ]; then
    echo "  System packages already installed — skipping apt-get update."
    return
  fi
  echo "  Installing missing system packages (sudo): ${missing[*]}"
  sudo apt-get update
  sudo apt-get install -y "${missing[@]}"
}

ensure_venv() {
  if [ ! -d "$VENV_DIR" ]; then
    echo "  Creating virtual environment with --system-site-packages..."
    python3 -m venv --system-site-packages "$VENV_DIR"
  else
    echo "  Virtual environment: exists"
  fi
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  echo "  Installing Python dependencies..."
  pip install -q --upgrade pip
  pip install -q -r "$SCRIPT_DIR/requirements.txt"
}

config_is_valid() {
  PYTHONPATH="$SCRIPT_DIR" "$VENV_DIR/bin/python" -c '
from talk_to_vibe.config.loader import load_config
import sys
config = load_config()
sys.exit(0 if not config.validate() else 1)
' >/dev/null 2>&1
}

run_config_wizard() {
  if [ "$REUSE_CONFIG" -eq 1 ] && config_is_valid; then
    echo ""
    echo "🔧 Reusing existing valid TalkToVibe configuration"
    return
  fi
  echo ""
  echo "🔧 Running TalkToVibe configuration wizard"
  # Use -c (not heredoc) so stdin stays attached to the terminal — the wizard
  # calls input() and would otherwise see EOF immediately.
  PYTHONPATH="$SCRIPT_DIR" "$VENV_DIR/bin/python" -c '
from talk_to_vibe.config.wizard import run_wizard
run_wizard(force=True)
'
}

get_configured_provider() {
  PYTHONPATH="$SCRIPT_DIR" "$VENV_DIR/bin/python" -c '
from talk_to_vibe.config.loader import load_config
print(load_config().provider)
' 2>/dev/null
}

maybe_install_whisper() {
  local provider
  provider="$(get_configured_provider | tr -d '[:space:]' || true)"
  if [ "$provider" != "local_whisper" ]; then
    return
  fi
  if "$VENV_DIR/bin/python" -c "import faster_whisper" >/dev/null 2>&1; then
    echo "  faster-whisper already installed in venv — skipping local Whisper installer"
    return
  fi
  echo ""
  echo "🧠 local_whisper provider selected but faster-whisper isn't installed in the venv."
  echo "   Handing off to ./linux_install_and_set_whisper.sh to install dependencies and the model."
  echo ""
  local whisper_args=(--skip-config)
  if [ "$AUTO_YES" -eq 1 ]; then
    whisper_args+=(--yes)
  fi
  bash "$SCRIPT_DIR/linux_install_and_set_whisper.sh" "${whisper_args[@]}"
}

write_launcher() {
  mkdir -p "$USER_BIN"
  cat > "$LAUNCHER" <<EOF
#!/bin/bash
exec "$SCRIPT_DIR/run_ttv.sh" "\$@"
EOF
  chmod +x "$LAUNCHER"
  echo "  Wrote launcher: $LAUNCHER"
}

write_desktop_entry() {
  mkdir -p "$DESKTOP_DIR"
  cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME
GenericName=Push-to-talk transcription
Comment=Vibe code with your voice, not your keyboard
Exec=$LAUNCHER
Icon=audio-input-microphone
Terminal=false
Categories=Utility;AudioVideo;
StartupNotify=false
Keywords=speech;voice;transcription;dictation;
EOF
  echo "  Wrote desktop entry: $DESKTOP_FILE"
}

prompt_autostart() {
  if [ "$SKIP_AUTOSTART" -eq 1 ]; then
    return
  fi
  if [ "$ENABLE_AUTOSTART" -eq 1 ]; then
    install_autostart
    return
  fi
  if confirm "Launch TalkToVibe at login?" "y"; then
    install_autostart
  else
    remove_autostart
  fi
}

install_autostart() {
  mkdir -p "$AUTOSTART_DIR"
  cat > "$AUTOSTART_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME
Exec=$LAUNCHER
Icon=audio-input-microphone
Terminal=false
X-GNOME-Autostart-enabled=true
StartupNotify=false
Comment=Push-to-talk transcription
EOF
  echo "  Autostart enabled: $AUTOSTART_FILE"
}

remove_autostart() {
  rm -f "$AUTOSTART_FILE"
  echo "  Autostart disabled"
}

show_post_install_help() {
  echo ""
  echo "✅ Installation complete"
  echo "  Launcher:       $LAUNCHER"
  echo "  Desktop entry:  $DESKTOP_FILE"
  if [ -f "$AUTOSTART_FILE" ]; then
    echo "  Autostart:      enabled"
  else
    echo "  Autostart:      disabled"
  fi
  echo ""
  echo "Run TalkToVibe:"
  echo "  talktovibe                       # via launcher in ~/.local/bin"
  echo "  $SCRIPT_DIR/run_ttv.sh           # directly from the repo"
  echo ""
  echo "Reconfigure:"
  echo "  $SCRIPT_DIR/run_ttv.sh --setup"
  echo ""
  echo "Uninstall:"
  echo "  $SCRIPT_DIR/uninstall_linux.sh"
}

launch_app() {
  if [ "$NO_LAUNCH" -eq 1 ]; then
    return
  fi
  if confirm "Launch TalkToVibe now?" "y"; then
    nohup "$LAUNCHER" >/dev/null 2>&1 &
    echo "  Launched in background"
  fi
}

main() {
  parse_args "$@"
  ensure_linux
  ensure_python3
  ensure_x11

  echo "🎤 TalkToVibe Linux Setup"
  echo "========================="
  install_apt_deps
  ensure_venv
  run_config_wizard
  maybe_install_whisper
  write_launcher
  write_desktop_entry
  prompt_autostart
  show_post_install_help
  launch_app
}

main "$@"
