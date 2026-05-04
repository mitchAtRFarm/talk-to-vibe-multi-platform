# 🎤 Talk to Vibe

**Vibe code with your voice, not your keyboard.**

Press your configured chord once to start recording, speak, then press it again to transcribe and auto-paste. Dictate prompts, comments, commit messages, or anything else without leaving your keyboard.

## Quick Start

### macOS Installed App

```bash
# 1. Clone
git clone https://github.com/woohoyang-oss/talk-to-vibe.git
cd talk-to-vibe

# 2. Install TalkToVibe.app
./setup_macos.sh
```

This installs `TalkToVibe.app` into `~/Applications`, builds an installed reconfigure helper, optionally enables launch at login, and guides you through the required macOS permissions.

Launch the app from `~/Applications/TalkToVibe.app`. It runs as a menu bar app and does not require Terminal to stay open or focused.

### Linux Installed App (X11)

```bash
# 1. Clone
git clone https://github.com/woohoyang-oss/talk-to-vibe.git
cd talk-to-vibe

# 2. Install (apt-installs system deps, builds venv, writes desktop entry,
#    optionally enables autostart)
./setup_linux.sh
```

Tested on Ubuntu 24.04 + Cinnamon 6 (X11). Lands a system-tray icon (`AppIndicator`/`StatusNotifierItem`) with the same Provider Info / Auto-Enter / Reconfigure / About / Quit menu as the macOS menu bar app. Icon swaps between idle (mic), recording (red dot), and transcribing (hourglass) states. Notifications use `notify-send`.

> Wayland is **not supported** — global hotkey capture via pynput requires X11. Log out and pick a Cinnamon (X11) session at the login screen if your default is Wayland.

### Generic Repo Setup

```bash
# 1. Clone
git clone https://github.com/woohoyang-oss/talk-to-vibe.git
cd talk-to-vibe

# 2. Setup
bash setup.sh

# 3. Run
./run_ttv.sh
```

First run will ask you to choose an STT provider, enter your API key, and select a Push-to-Talk key.

## STT Providers

Talk to Vibe supports two types of speech-to-text providers:

| Provider | Type | Default Model | API Shape | Cost | Get Key |
|----------|------|---------------|-----------|------|---------|
| **Groq** | Whisper transcription | whisper-large-v3-turbo | `/audio/transcriptions` | Free tier | [console.groq.com](https://console.groq.com/keys) |
| **OpenAI** | Whisper transcription | whisper-1 | `/audio/transcriptions` | Paid | [platform.openai.com](https://platform.openai.com/api-keys) |
| **OpenAI-Compatible** | Whisper transcription | whisper-1 | `/audio/transcriptions` | Varies | Your own endpoint |
| **OpenRouter** | Multimodal chat | google/gemini-3.1-flash-lite-preview | `/chat/completions` + `input_audio` | Paid | [openrouter.ai](https://openrouter.ai/settings/keys) |

### Whisper Transcription vs Multimodal Chat

**Whisper-type providers** (Groq, OpenAI, OpenAI-Compatible) call the OpenAI `/audio/transcriptions` endpoint — purpose-built for speech-to-text. You upload a WAV file and get back a transcript. These are the simplest and most reliable for pure dictation.

**OpenRouter** calls the `/chat/completions` endpoint with a base64-encoded WAV as `input_audio`. This works with modern multimodal models (Gemini, GPT-4o, etc.) that can natively understand audio. It's more flexible — any model on OpenRouter that supports audio input can be used — but requires a chat prompt and parses the transcript from a chat response.

### Switch Provider

```bash
./run_ttv.sh --setup                # Re-run setup wizard
./run_ttv.sh --provider openrouter  # One-off override (not saved)
```

On macOS, the installed app also includes a `Reconfigure...` menu item in the menu bar app.

## Usage

1. Launch `TalkToVibe.app` from `~/Applications` on macOS, or run `./run_ttv.sh` for terminal/dev mode
2. Switch to any app (IDE, browser, Claude, etc.)
3. Press your configured push-to-talk chord once and speak
4. Press the chord again to transcribe and auto-paste the result

### Change PTT Key

PTT key is configured during setup and saved to config. You can also override it per-run:

```bash
./run_ttv.sh --key ctrl+9      # Control + 9 (recommended on Mac laptops)
./run_ttv.sh --key ctrl+1      # Control + 1
./run_ttv.sh --key ctrl+2      # Control + 2
./run_ttv.sh --key f18         # F18 (good on full keyboards)
./run_ttv.sh --key f19         # F19
./run_ttv.sh --setup           # Re-run setup to change saved key
```

Available keys (macOS): `ctrl+9` (default), `ctrl+1`, `ctrl+2`, `ctrl+3`, `ctrl+4`, `ctrl+5`, number keys `0-9`, `f18`, `f19`, `f20`, `f9`, `f10`, `f11`, `f12`, plus modifier-based keys like `alt_r`, `alt_l`, `cmd_r`, `ctrl_r`, and generic modifiers `ctrl`, `alt`, `cmd`, `shift`. Combine with `+` for chords like `ctrl+9` or `ctrl+f18`.

Available keys (Linux/X11): `ctrl+9` (default), number keys `0-9`, `f1`-`f20`, generic and side-specific modifiers (`ctrl`, `ctrl_l`, `ctrl_r`, `alt`, `alt_l`, `alt_r`, `shift`, `shift_l`, `shift_r`, `super`, `super_l`, `super_r`). Combine with `+` for chords like `ctrl+9` or `ctrl+shift_l+f12`.

On macOS, avoid modifier-only bindings like `ctrl+shift` or `alt_r`; they are collision-prone and unreliable with global event taps. On Mac laptops, prefer `ctrl+9`-style chords because the top-row keys often arrive as media/system events instead of normal function keys.

On Linux, watch out for shortcuts your DE has already claimed — Cinnamon's keyboard settings let you inspect global bindings. `ctrl+9` is unlikely to collide; modifier-only chords work but may surprise you if other panel applets respond to them.

### Custom Transcription Prompt

By default, Talk to Vibe uses a bundled transcription prompt optimized for coding — it tells the LLM to preserve file paths, identifiers, and code formatting. You can override it with your own `.md` file:

```yaml
# ~/.talktovibe/config.yaml
prompt_file: ~/my_prompts/transcription.md
```

Set `prompt_file` to an empty string (or omit it) to use the bundled prompt. Run `./run_ttv.sh --setup` or use the macOS app's `Reconfigure...` menu item to configure it interactively.

## macOS Permissions

On first launch of `TalkToVibe.app`, grant these in **System Settings → Privacy & Security**:

- **Accessibility** → Allow `TalkToVibe.app`
- **Microphone** → Allow `TalkToVibe.app`
- Some systems may also require **Input Monitoring** for global key listening

> Without Accessibility permission, auto-paste (Cmd+V simulation) will not work.

## Linux Permissions / Notes

X11 imposes no special permission model for global key listening — anything that can connect to your X server can listen. Concrete requirements:

- An **X11 session** (Cinnamon, GNOME on Xorg, KDE on Xorg, XFCE, MATE). Wayland is not supported.
- A **clipboard tool**: `xclip` (preferred), `xsel`, or `wl-clipboard` — `setup_linux.sh` installs `xclip`.
- A working **PulseAudio or PipeWire** stack, with the user in the `audio` group (default on Ubuntu).
- An **AppIndicator/StatusNotifierItem** host in the panel — Cinnamon's XApp Status Applet handles this natively. On stock GNOME you also need the `gnome-shell-extension-appindicator` extension enabled.

## Linux Install And Uninstall

Install:

```bash
./setup_linux.sh
```

Useful flags:

```bash
./setup_linux.sh --yes              # accept defaults
./setup_linux.sh --skip-apt         # skip apt-get if deps already installed
./setup_linux.sh --skip-autostart   # don't ask about launch-at-login
./setup_linux.sh --enable-autostart # enable autostart without prompting
./setup_linux.sh --reuse-config     # don't re-run wizard if config is valid
./setup_linux.sh --no-launch        # don't auto-launch after install
```

The installer apt-installs `libportaudio2 xclip libayatana-appindicator3-1 gir1.2-ayatanaappindicator3-0.1 python3-gi python3-gi-cairo libcanberra-gtk3-module libnotify-bin python3-venv`, creates a `--system-site-packages` venv in the repo, runs the configuration wizard, writes a launcher at `~/.local/bin/talktovibe`, a `.desktop` entry at `~/.local/share/applications/TalkToVibe.desktop`, and (optionally) an autostart entry at `~/.config/autostart/TalkToVibe.desktop`.

Uninstall:

```bash
./uninstall_linux.sh
```

Useful flags:

```bash
./uninstall_linux.sh --keep-config    # preserve ~/.talktovibe/config.yaml
./uninstall_linux.sh --remove-venv    # also delete .venv
./uninstall_linux.sh --yes            # accept defaults
```

`uninstall_linux.sh` removes the launcher, desktop entry, autostart entry, logs, and config by default. It does **not** apt-uninstall system packages — run `sudo apt-get remove <pkg>` yourself if you want them gone.

## macOS Install And Uninstall

Install or repair the packaged app:

```bash
./setup_macos.sh
```

Useful installer flags:

```bash
./setup_macos.sh --yes
./setup_macos.sh --skip-login-item
./setup_macos.sh --no-launch
./setup_macos.sh --rebuild
./setup_macos.sh --skip-signing
```

Uninstall the packaged app and its installed support files outside the repo:

```bash
./uninstall_macos.sh
```

Useful uninstall flags:

```bash
./uninstall_macos.sh --keep-config
./uninstall_macos.sh --remove-brew-deps
./uninstall_macos.sh --yes
```

`uninstall_macos.sh` removes the installed app, installed helper, LaunchAgent, logs, and config by default. It does not remove anything inside the cloned repository.

## How It Works

```
Press PTT Chord → Microphone → STT Provider API → Clipboard → Auto Paste
```

- **Audio**: 16kHz, 16-bit, mono WAV
- **Mic**: Auto-detects real hardware mic (skips virtual devices like BlackHole)
- **Output (macOS)**: pbcopy + pynput Cmd+V simulation
- **Output (Linux)**: xclip (or xsel/wl-copy fallback) + pynput Ctrl+V simulation
- **Installed app logs**: `~/.talktovibe/logs/app.log`

## Architecture

```
talk_to_vibe/
  config/       — YAML config models, loader, wizard
  audio/        — microphone recording, WAV helpers
  providers/    — STT backends (groq, openai, openai_compatible, openrouter)
  providers/prompts/ — Bundled .md prompt files and loader
  platforms/    — OS-specific behavior (macOS + Linux active, Windows stub)
  app.py        — main app loop (terminal mode)
  menubar.py    — rumps menu bar app (macOS default)
  tray.py       — pystray AppIndicator tray app (Linux default)
  cli.py        — argument parsing and entry point wiring
  errors.py     — custom exceptions
tests/          — unit tests
```

## Config

Stored at `~/.talktovibe/config.yaml` (chmod 600)

```yaml
provider: openrouter
ptt_key: ctrl+9
auto_enter: false
prompt_file: ""

providers:
  groq:
    api_key: gsk_...
    model: whisper-large-v3-turbo
  openai:
    api_key: sk-...
    model: whisper-1
  openai_compatible:
    base_url: http://localhost:8000/v1
    api_key: ""
    model: whisper-1
  openrouter:
    api_key: sk-or-...
    model: google/gemini-3.1-flash-lite-preview
    base_url: https://openrouter.ai/api/v1/chat/completions
```

All configuration is managed via YAML. Models, base URLs, and API keys are defined in config — nothing is hardcoded in the Python code.

- **`prompt_file`**: Path to a custom `.md` transcription prompt. Empty string uses the bundled coding-aware prompt. See [Custom Transcription Prompt](#custom-transcription-prompt).

## Running Tests

```bash
./run_ttv.sh --test
```

## License

MIT
