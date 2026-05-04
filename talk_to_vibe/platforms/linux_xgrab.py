"""X11 chord grabber.

pynput's keyboard listener on X11 uses XRecord, which is *observation only* —
the focused application still receives the key. For PTT chords like Ctrl+9
that means the `9` leaks into the focused window (e.g. a terminal).

This module sits alongside the pynput listener and calls XGrabKey on the
chord. Once grabbed, the X server delivers those key events only to us, so
the focused window never sees them. pynput's XRecord listener keeps working
in parallel and continues to drive the state machine.

We don't act on the grabbed events ourselves — we just drain them so the X
queue doesn't back up.
"""
from __future__ import annotations

import logging
import threading
from typing import Iterable


_MOD_MASK_NAMES = {
    "ctrl": "ControlMask",
    "ctrl_l": "ControlMask",
    "ctrl_r": "ControlMask",
    "shift": "ShiftMask",
    "shift_l": "ShiftMask",
    "shift_r": "ShiftMask",
    "alt": "Mod1Mask",
    "alt_l": "Mod1Mask",
    "alt_r": "Mod1Mask",
    "super": "Mod4Mask",
    "super_l": "Mod4Mask",
    "super_r": "Mod4Mask",
    "cmd": "Mod4Mask",
    "cmd_l": "Mod4Mask",
    "cmd_r": "Mod4Mask",
}

_KEYSYM_BY_TOKEN = {
    "0": "0", "1": "1", "2": "2", "3": "3", "4": "4",
    "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",
}
for _n in range(1, 21):
    _KEYSYM_BY_TOKEN[f"f{_n}"] = f"F{_n}"


def _split_chord(chord_str: str) -> list[str]:
    return [p.strip().lower() for p in chord_str.split("+") if p.strip()]


def chord_components(chord_str: str) -> tuple[list[str], str | None]:
    """Split a chord into (modifier_tokens, primary_key_token).

    Examples:
      "ctrl+9"       -> (["ctrl"], "9")
      "ctrl+alt_r+f18" -> (["ctrl", "alt_r"], "f18")
      "alt_r"        -> (["alt_r"], None)  # modifier-only chord
    """
    parts = _split_chord(chord_str)
    mods: list[str] = []
    primary: str | None = None
    for p in parts:
        if p in _MOD_MASK_NAMES:
            mods.append(p)
        else:
            primary = p
    return mods, primary


class XChordGrabber:
    """Grab a chord at the X server so it doesn't leak to focused windows.

    Safe to instantiate on non-X11 / Wayland systems; .start() will return
    False and become a no-op.
    """

    def __init__(self, chord_str: str, logger: logging.Logger | None = None):
        self.chord_str = chord_str
        self.logger = logger or logging.getLogger(__name__)
        self._display = None
        self._root = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._grabs: list[tuple[int, int]] = []

    def start(self) -> bool:
        try:
            from Xlib import X, display
            from Xlib import error as xerror
        except Exception as exc:
            self.logger.warning("python-xlib unavailable; chord grab disabled: %s", exc)
            return False

        mods, primary = chord_components(self.chord_str)
        if primary is None:
            self.logger.info(
                "Chord %r is modifier-only; nothing to grab (no key leak risk).",
                self.chord_str,
            )
            return False
        keysym_name = _KEYSYM_BY_TOKEN.get(primary)
        if not keysym_name:
            self.logger.info(
                "Chord %r has no XGrabKey mapping for primary key %r; skipping grab.",
                self.chord_str, primary,
            )
            return False

        try:
            self._display = display.Display()
        except Exception as exc:
            self.logger.warning("Cannot open X display for chord grab: %s", exc)
            return False

        try:
            from Xlib import XK
            keysym = getattr(XK, f"XK_{keysym_name}", None)
            if keysym is None:
                self.logger.warning("Unknown keysym XK_%s for chord %r", keysym_name, self.chord_str)
                self._close_display()
                return False
            keycode = self._display.keysym_to_keycode(keysym)
            if not keycode:
                self.logger.warning("No keycode for keysym XK_%s on this server", keysym_name)
                self._close_display()
                return False

            base_mask = 0
            for m in mods:
                attr = _MOD_MASK_NAMES.get(m)
                if attr:
                    base_mask |= getattr(X, attr)

            # Grab all four combinations of NumLock (Mod2) / CapsLock (Lock)
            # so the grab still triggers regardless of toggle state.
            lock_combinations = [
                0,
                X.LockMask,
                X.Mod2Mask,
                X.LockMask | X.Mod2Mask,
            ]

            self._root = self._display.screen().root
            for extra in lock_combinations:
                mask = base_mask | extra
                try:
                    self._root.grab_key(
                        keycode,
                        mask,
                        True,
                        X.GrabModeAsync,
                        X.GrabModeAsync,
                    )
                    self._grabs.append((keycode, mask))
                except xerror.BadAccess:
                    self.logger.warning(
                        "Chord %r already grabbed by another client (mask=0x%x); leak may persist.",
                        self.chord_str, mask,
                    )
                except Exception:
                    self.logger.exception(
                        "Failed to grab chord %r with mask 0x%x", self.chord_str, mask
                    )

            self._display.sync()
            self._display.flush()
        except Exception:
            self.logger.exception("Chord grab setup failed for %r", self.chord_str)
            self._close_display()
            return False

        if not self._grabs:
            self._close_display()
            return False

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._drain_loop, name="x11-chord-drain", daemon=True
        )
        self._thread.start()
        self.logger.info(
            "X11 chord grab active for %r (keycode=%d, %d mask variants)",
            self.chord_str, keycode, len(self._grabs),
        )
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._display is not None and self._root is not None:
            try:
                for keycode, mask in self._grabs:
                    self._root.ungrab_key(keycode, mask)
                self._display.sync()
            except Exception:
                self.logger.exception("Failed to ungrab chord %r", self.chord_str)
        self._grabs.clear()
        self._close_display()

    def _drain_loop(self) -> None:
        # Pull events and discard. We rely on pynput's XRecord listener to
        # deliver the chord trigger to the application logic; we just need to
        # keep our own X queue from filling up.
        try:
            while not self._stop.is_set():
                if self._display is None:
                    return
                if self._display.pending_events():
                    self._display.next_event()
                else:
                    # No events ready — sleep briefly. We can't block on
                    # next_event() because stop() needs to interrupt cleanly.
                    self._stop.wait(0.05)
        except Exception:
            self.logger.exception("Chord drain loop crashed for %r", self.chord_str)

    def _close_display(self) -> None:
        if self._display is not None:
            try:
                self._display.close()
            except Exception:
                pass
        self._display = None
        self._root = None
