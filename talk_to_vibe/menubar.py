import logging
from pathlib import Path
import signal
import subprocess
import threading
import time

import rumps

from talk_to_vibe.audio.recorder import AudioRecorder
from talk_to_vibe.providers.base import BaseSTTProvider
from talk_to_vibe.platforms.detect import get_platform
from talk_to_vibe import __version__
from talk_to_vibe.config.loader import load_config, save_config
from talk_to_vibe.runtime_paths import APP_BUNDLE_NAME, APP_NAME, INSTALLED_CONFIGURE_HELPER_PATH, configure_file_logging

TITLE_IDLE = "🎤"
TITLE_RECORDING = "🔴"
TITLE_TRANSCRIBING = "⏳"


class TalkToVibeMenuBar(rumps.App):
    def __init__(self, stt: BaseSTTProvider, ptt_key_name: str = "alt_r", auto_enter: bool = False, prompt_file: str = ""):
        super().__init__(TITLE_IDLE, quit_button=None)
        self.logger = configure_file_logging("talktovibe.menubar")
        self.stt = stt
        self.ptt_key_name = ptt_key_name
        self.auto_enter = auto_enter
        self.prompt_file = prompt_file
        self.platform = get_platform()
        self.recorder = AudioRecorder(error_callback=self._handle_recorder_error)
        self.is_recording = False
        self.processing = False
        self.ptt_chord = self.platform.parse_ptt_chord(ptt_key_name)
        self.held_keys: set = set()
        self._chord_armed = False
        self._paste_in_progress = False
        self._pending_title: str | None = None
        self._title_timer = rumps.Timer(self._apply_pending_title, 0.1)
        self._title_timer.start()

        self._auto_enter_item = rumps.MenuItem(
            f"Auto-Enter: {'ON ✅' if auto_enter else 'OFF'}",
            callback=self._toggle_auto_enter,
        )
        self.menu = [
            rumps.MenuItem("Provider Info", callback=self._show_provider_info),
            self._auto_enter_item,
            None,
            rumps.MenuItem("Reconfigure...", callback=self._reconfigure),
            None,
            rumps.MenuItem("About", callback=self._show_about),
            rumps.MenuItem("Quit", callback=self._quit),
        ]

    def _notify(self, subtitle: str, message: str):
        try:
            rumps.notification(APP_NAME, subtitle, message)
        except Exception:
            self.logger.exception("Failed to send notification: %s - %s", subtitle, message)

    def _alert(self, title: str, message: str):
        try:
            rumps.alert(title, message)
        except Exception:
            self.logger.exception("Failed to show alert: %s - %s", title, message)

    def _handle_recorder_error(self, message: str):
        self.logger.error(message)
        self._notify("Microphone", message[:150])
        self._alert("Microphone Access", message)

    def _ensure_global_key_access(self) -> bool:
        status = self.platform.get_global_key_access_status()
        if all(status.values()):
            return True

        self.logger.warning("Global key access is not granted for ptt_key=%s status=%s", self.ptt_key_name, status)
        self.platform.request_global_key_access()
        permission_lines = "\n".join(self.platform.get_global_key_permission_help())
        self._notify(
            "Permissions Required",
            f"TalkToVibe may need Input Monitoring or Accessibility for {self.ptt_key_name}. Check System Settings if the hotkey does not work.",
        )
        self.logger.warning("Global key access help for ptt_key=%s:\n%s", self.ptt_key_name, permission_lines)
        return False

    def _set_title(self, title: str):
        self._pending_title = title

    def _apply_pending_title(self, _):
        if self._pending_title is not None:
            self.title = self._pending_title
            self._pending_title = None

    def _start_listener(self):
        try:
            from pynput import keyboard

            has_access = self._ensure_global_key_access()
            listener_kwargs = self.platform.build_listener_kwargs(self.logger)

            listener = keyboard.Listener(
                on_press=self.on_key_press,
                on_release=self.on_key_release,
                **listener_kwargs,
            )
            listener.daemon = True
            listener.start()
            chord_display = self.platform.get_chord_display_name(self.ptt_key_name)
            self.logger.info("Started global keyboard listener for ptt_key=%s (%s)", self.ptt_key_name, chord_display)
            if not has_access:
                self.logger.warning(
                    "Listener started despite missing preflight access for ptt_key=%s; waiting to see if macOS actually delivers events",
                    self.ptt_key_name,
                )
            if hasattr(listener, "_thread") and listener._thread is not None:
                thread = listener._thread

                def log_listener_failure():
                    thread.join()
                    if not getattr(listener, "running", False):
                        self.logger.warning("Global keyboard listener thread exited for ptt_key=%s", self.ptt_key_name)

                threading.Thread(target=log_listener_failure, daemon=True).start()
        except Exception as exc:
            self.logger.exception("Failed to start global keyboard listener for ptt_key=%s", self.ptt_key_name)
            self._alert(
                "Global Key Listener Error",
                f"TalkToVibe failed to start the global keyboard listener for {self.ptt_key_name}.\n\n{exc}",
            )

    def on_key_press(self, key):
        if self._paste_in_progress:
            return

        normalized_key = self.platform.normalize_listener_key(key)
        self.logger.info(
            "Key press raw=%s normalized=%s held_before=%s target=%s",
            self.platform.describe_listener_key(key),
            repr(normalized_key),
            sorted(repr(k) for k in self.held_keys),
            sorted(repr(k) for k in self.ptt_chord),
        )
        self.held_keys.add(normalized_key)

        if self.processing:
            return

        if self.held_keys != self.ptt_chord:
            return

        if self._chord_armed:
            return

        self._chord_armed = True
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        self.is_recording = True
        self._set_title(TITLE_RECORDING)
        self.logger.info("Recording started for ptt_key=%s", self.ptt_key_name)
        if not self.recorder.start():
            self.is_recording = False
            self._set_title(TITLE_IDLE)

    def _stop_recording(self):
        self.is_recording = False
        self.logger.info("Recording stopped for ptt_key=%s", self.ptt_key_name)
        audio_data, duration = self.recorder.stop()

        if audio_data is None:
            self._set_title(TITLE_IDLE)
            return

        self.processing = True
        self._set_title(TITLE_TRANSCRIBING)
        threading.Thread(target=self._process, args=(audio_data, duration), daemon=True).start()

    def on_key_release(self, key):
        if self._paste_in_progress:
            return

        normalized_key = self.platform.normalize_listener_key(key)
        self.logger.info(
            "Key release raw=%s normalized=%s held_before=%s target=%s",
            self.platform.describe_listener_key(key),
            repr(normalized_key),
            sorted(repr(k) for k in self.held_keys),
            sorted(repr(k) for k in self.ptt_chord),
        )
        self.held_keys.discard(normalized_key)

        if normalized_key in self.ptt_chord and self.held_keys != self.ptt_chord:
            self._chord_armed = False

    def _process(self, audio_data, duration):
        try:
            start = time.time()
            text = self.stt.transcribe(audio_data)
            elapsed = time.time() - start
            self.logger.info("Transcription completed in %.2fs", elapsed)

            if text:
                self._paste_in_progress = True
                try:
                    self.platform.paste_text(text, auto_enter=self.auto_enter)
                finally:
                    self._paste_in_progress = False
                self.platform.play_success_sound()
                self._notify(f"Transcribed ({elapsed:.1f}s)", text[:100])
            else:
                self._notify("Empty", "No speech detected")
        except Exception as e:
            self.logger.exception("Transcription failed")
            self._notify("Error", str(e)[:100])
        finally:
            self.processing = False
            self._set_title(TITLE_IDLE)

    def _toggle_auto_enter(self, _):
        self.auto_enter = not self.auto_enter
        self._auto_enter_item.title = f"Auto-Enter: {'ON ✅' if self.auto_enter else 'OFF'}"
        config = load_config()
        config.auto_enter = self.auto_enter
        save_config(config)

    def _show_provider_info(self, _):
        chord_display = self.platform.get_chord_display_name(self.ptt_key_name)
        self._alert(
            "Provider Info",
            f"Provider: {self.stt.provider_name}\n"
            f"Model: {self.stt.model}\n"
            f"PTT Key: {chord_display}\n"
            f"Auto-Enter: {'ON' if self.auto_enter else 'OFF'}",
        )

    def _reconfigure(self, _):
        helper_path = INSTALLED_CONFIGURE_HELPER_PATH
        if helper_path.exists():
            command = ["open", "-a", "Terminal", str(helper_path), "--setup"]
            self.logger.info("Launching installed reconfigure helper: %s", command)
            subprocess.Popen(command)
            self._alert("Reconfigure", f"Follow the prompts in the Terminal window.\nQuit and relaunch {APP_BUNDLE_NAME} when done.")
            return

        repo_run_ttv = Path(__file__).resolve().parents[1] / "run_ttv.sh"
        if repo_run_ttv.exists():
            command = ["open", "-a", "Terminal", repo_run_ttv, "--setup"]
            self.logger.info("Launching repo reconfigure helper: %s", command)
            subprocess.Popen(command)
            self._alert("Reconfigure", f"Follow the prompts in the Terminal window.\nQuit and relaunch {APP_BUNDLE_NAME} when done.")
            return

        self.logger.warning("No configure helper found at %s or in repo checkout", helper_path)
        self._alert(
            "Reconfigure",
            "No setup helper was found. Re-run ./setup_macos.sh from the repo to repair the installation.",
        )

    def _show_about(self, _):
        self._alert("About TalkToVibe", f"TalkToVibe v{__version__}\nPush-to-talk speech-to-text")

    def _cleanup(self):
        if self.is_recording:
            self.is_recording = False
            self.recorder.stop()
        self._chord_armed = False
        self.held_keys.clear()

    def _quit(self, _):
        self._cleanup()
        rumps.quit_application()

    def run(self):
        self.logger.info("Launching menu bar app with ptt_key=%s", self.ptt_key_name)
        self._start_listener()
        original_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self._handle_sigint)
        try:
            super().run()
        finally:
            signal.signal(signal.SIGINT, original_handler)
            self.logger.info("Menu bar app exiting")

    def _handle_sigint(self, signum, frame):
        self._cleanup()
        rumps.quit_application()
