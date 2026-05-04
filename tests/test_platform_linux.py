from unittest.mock import patch, MagicMock

import pytest

from talk_to_vibe.platforms.linux import LinuxPlatform
from talk_to_vibe.errors import PlatformError


class TestLinuxKeyMap:
    def test_default_ptt_key(self):
        assert LinuxPlatform().get_default_ptt_key() == "ctrl+9"

    def test_key_map_has_modifiers(self):
        key_map = LinuxPlatform().get_key_map()
        for k in ("alt", "alt_l", "alt_r", "ctrl", "ctrl_l", "ctrl_r", "shift", "shift_l", "shift_r", "super", "cmd"):
            assert k in key_map, f"missing key {k}"

    def test_key_map_has_digits(self):
        key_map = LinuxPlatform().get_key_map()
        for digit in "0123456789":
            assert digit in key_map

    def test_key_map_has_function_keys(self):
        key_map = LinuxPlatform().get_key_map()
        for n in range(1, 13):
            assert f"f{n}" in key_map

    def test_display_names_cover_all_keys(self):
        names = LinuxPlatform().get_key_display_names()
        assert "Ctrl" in names["ctrl"]
        assert names["9"] == "9"
        assert names["f9"] == "F9"
        assert "Super" in names["super"]


class TestLinuxParseChord:
    def test_single_modifier(self):
        p = LinuxPlatform()
        result = p.parse_ptt_chord("alt_r")
        assert result == frozenset({p.get_key_map()["alt"]})

    def test_modifier_plus_digit(self):
        p = LinuxPlatform()
        result = p.parse_ptt_chord("ctrl+9")
        km = p.get_key_map()
        assert result == frozenset({km["ctrl"], km["9"]})

    def test_three_key_chord(self):
        p = LinuxPlatform()
        result = p.parse_ptt_chord("ctrl+shift_l+f12")
        km = p.get_key_map()
        assert result == frozenset({km["ctrl"], km["shift"], km["f12"]})

    def test_side_specific_modifier_chord_normalizes_to_runtime_keys(self):
        p = LinuxPlatform()
        km = p.get_key_map()
        result = p.parse_ptt_chord("ctrl+alt_r")
        assert result == frozenset({km["ctrl"], km["alt"]})

    def test_unknown_key_raises(self):
        with pytest.raises(PlatformError, match="Unknown key"):
            LinuxPlatform().parse_ptt_chord("nonexistent")

    def test_unknown_key_in_chord_raises(self):
        with pytest.raises(PlatformError, match="Unknown key"):
            LinuxPlatform().parse_ptt_chord("ctrl+nope")

    def test_empty_chord_raises(self):
        with pytest.raises(PlatformError, match="Empty chord"):
            LinuxPlatform().parse_ptt_chord("")

    def test_whitespace_only_chord_raises(self):
        with pytest.raises(PlatformError, match="Empty chord"):
            LinuxPlatform().parse_ptt_chord("  +  ")


class TestLinuxChordDisplay:
    def test_modifier_plus_digit(self):
        text = LinuxPlatform().get_chord_display_name("ctrl+9")
        assert "Ctrl" in text
        assert "9" in text
        assert "+" in text

    def test_function_key(self):
        assert "F12" in LinuxPlatform().get_chord_display_name("f12")


class TestLinuxModifierOnly:
    def test_single_modifier_is_modifier_only(self):
        assert LinuxPlatform().is_modifier_only("alt_r") is True

    def test_modifier_plus_digit_is_not_modifier_only(self):
        assert LinuxPlatform().is_modifier_only("ctrl+9") is False

    def test_function_key_is_not_modifier_only(self):
        assert LinuxPlatform().is_modifier_only("f12") is False

    def test_chord_all_modifiers(self):
        assert LinuxPlatform().is_modifier_only("ctrl+alt") is True

    def test_empty_returns_false(self):
        assert LinuxPlatform().is_modifier_only("") is False


class TestLinuxNormalizeListenerKey:
    def test_side_modifiers_collapse_to_generic(self):
        from pynput import keyboard
        p = LinuxPlatform()
        assert p.normalize_listener_key(keyboard.Key.alt_l) == keyboard.Key.alt
        assert p.normalize_listener_key(keyboard.Key.alt_r) == keyboard.Key.alt
        assert p.normalize_listener_key(keyboard.Key.ctrl_l) == keyboard.Key.ctrl
        assert p.normalize_listener_key(keyboard.Key.shift_r) == keyboard.Key.shift
        assert p.normalize_listener_key(keyboard.Key.cmd_l) == keyboard.Key.cmd

    def test_non_modifier_key_unchanged(self):
        from pynput import keyboard
        p = LinuxPlatform()
        digit = keyboard.KeyCode.from_char("9")
        assert p.normalize_listener_key(digit) == digit

    def test_describe_listener_key_shows_normalization(self):
        from pynput import keyboard
        text = LinuxPlatform().describe_listener_key(keyboard.Key.alt_l)
        assert "alt" in text.lower()


class TestLinuxPaste:
    def test_paste_populates_clipboard_via_xclip(self):
        p = LinuxPlatform()
        # xclip available, xdotool missing → falls back to pynput typing.
        with patch(
            "talk_to_vibe.platforms.linux.shutil.which",
            side_effect=lambda name: f"/usr/bin/{name}" if name == "xclip" else None,
        ), patch("talk_to_vibe.platforms.linux.subprocess.Popen") as mock_popen, \
             patch("talk_to_vibe.platforms.linux.subprocess.run"), \
             patch("talk_to_vibe.platforms.linux.time"), \
             patch("pynput.keyboard.Controller"):
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc
            p.paste_text("hello")
            args = mock_popen.call_args[0][0]
            assert args[0] == "xclip"
            # Clipboard receives the text. Allow the timeout kwarg.
            payload = mock_proc.communicate.call_args.args[0]
            assert payload == b"hello"

    def test_paste_uses_xdotool_type_when_available(self):
        p = LinuxPlatform()
        which_results = {"xclip": "/usr/bin/xclip", "xdotool": "/usr/bin/xdotool"}
        with patch(
            "talk_to_vibe.platforms.linux.shutil.which",
            side_effect=lambda name: which_results.get(name),
        ), patch("talk_to_vibe.platforms.linux.subprocess.Popen"), \
             patch("talk_to_vibe.platforms.linux.subprocess.run") as mock_run, \
             patch("talk_to_vibe.platforms.linux.time"):
            p.paste_text("hello world")
        # Expect at least one call with xdotool type.
        type_calls = [c for c in mock_run.call_args_list if c.args[0][:2] == ["xdotool", "type"]]
        assert type_calls, f"expected xdotool type call, got {mock_run.call_args_list}"
        assert "hello world" in type_calls[0].args[0]

    def test_paste_auto_enter_presses_enter_via_xdotool(self):
        p = LinuxPlatform()
        which_results = {"xclip": "/usr/bin/xclip", "xdotool": "/usr/bin/xdotool"}
        with patch(
            "talk_to_vibe.platforms.linux.shutil.which",
            side_effect=lambda name: which_results.get(name),
        ), patch("talk_to_vibe.platforms.linux.subprocess.Popen"), \
             patch("talk_to_vibe.platforms.linux.subprocess.run") as mock_run, \
             patch("talk_to_vibe.platforms.linux.time"):
            p.paste_text("hello", auto_enter=True)
        return_calls = [
            c for c in mock_run.call_args_list
            if c.args[0][:2] == ["xdotool", "key"] and "Return" in c.args[0]
        ]
        assert return_calls, f"expected xdotool key Return call, got {mock_run.call_args_list}"

    def test_paste_auto_enter_presses_enter_via_pynput_fallback(self):
        # No xdotool — falls back to pynput, which presses Key.enter.
        p = LinuxPlatform()
        with patch("talk_to_vibe.platforms.linux.shutil.which", side_effect=lambda name: "/usr/bin/xclip" if name == "xclip" else None), \
             patch("talk_to_vibe.platforms.linux.subprocess.Popen"), \
             patch("talk_to_vibe.platforms.linux.subprocess.run"), \
             patch("talk_to_vibe.platforms.linux.time"), \
             patch("pynput.keyboard.Controller") as mock_ctrl:
            from pynput.keyboard import Key
            p.paste_text("hello", auto_enter=True)
            kb = mock_ctrl.return_value
            press_keys = [c.args[0] for c in kb.press.call_args_list]
            assert Key.enter in press_keys

    def test_paste_falls_back_to_xsel(self):
        p = LinuxPlatform()
        which_results = {"xclip": None, "xsel": "/usr/bin/xsel", "wl-copy": None, "xdotool": None}
        with patch("talk_to_vibe.platforms.linux.shutil.which", side_effect=lambda name: which_results.get(name)), \
             patch("talk_to_vibe.platforms.linux.subprocess.Popen") as mock_popen, \
             patch("talk_to_vibe.platforms.linux.subprocess.run"), \
             patch("talk_to_vibe.platforms.linux.time"), \
             patch("pynput.keyboard.Controller"):
            p.paste_text("hello")
            args = mock_popen.call_args[0][0]
            assert args[0] == "xsel"

    def test_paste_proceeds_when_no_clipboard_tool(self):
        # No clipboard tool — we still type text into the focused window via
        # xdotool / pynput. Clipboard population is best-effort.
        p = LinuxPlatform()
        with patch("talk_to_vibe.platforms.linux.shutil.which", return_value=None), \
             patch("talk_to_vibe.platforms.linux.subprocess.Popen") as mock_popen, \
             patch("talk_to_vibe.platforms.linux.subprocess.run"), \
             patch("talk_to_vibe.platforms.linux.time"), \
             patch("pynput.keyboard.Controller") as mock_ctrl:
            p.paste_text("hello")
            mock_popen.assert_not_called()
            mock_ctrl.return_value.type.assert_called_once_with("hello")


class TestLinuxSuccessSound:
    def test_uses_canberra_when_available(self):
        p = LinuxPlatform()
        with patch("talk_to_vibe.platforms.linux.shutil.which", side_effect=lambda name: "/usr/bin/canberra-gtk-play" if name == "canberra-gtk-play" else None), \
             patch("talk_to_vibe.platforms.linux.subprocess.Popen") as mock_popen:
            p.play_success_sound()
            args = mock_popen.call_args[0][0]
            assert args[0] == "canberra-gtk-play"

    def test_falls_back_to_paplay(self):
        which_results = {"canberra-gtk-play": None, "paplay": "/usr/bin/paplay", "aplay": None}
        p = LinuxPlatform()
        with patch("talk_to_vibe.platforms.linux.shutil.which", side_effect=lambda name: which_results.get(name)), \
             patch("talk_to_vibe.platforms.linux.subprocess.Popen") as mock_popen:
            p.play_success_sound()
            args = mock_popen.call_args[0][0]
            assert args[0] == "paplay"

    def test_silent_when_no_player(self):
        p = LinuxPlatform()
        with patch("talk_to_vibe.platforms.linux.shutil.which", return_value=None), \
             patch("talk_to_vibe.platforms.linux.subprocess.Popen") as mock_popen:
            p.play_success_sound()
            mock_popen.assert_not_called()


class TestLinuxPermissionHelp:
    def test_x11_permission_help_is_brief(self):
        with patch.dict("os.environ", {"WAYLAND_DISPLAY": "", "XDG_SESSION_TYPE": "x11"}, clear=False):
            help_lines = LinuxPlatform().get_global_key_permission_help()
            assert len(help_lines) >= 1
            assert all("Wayland" not in line for line in help_lines)

    def test_wayland_permission_help_warns(self):
        with patch.dict("os.environ", {"WAYLAND_DISPLAY": "wayland-0"}, clear=False):
            help_lines = LinuxPlatform().get_global_key_permission_help()
            assert any("Wayland" in line for line in help_lines)
            assert any("X11" in line for line in help_lines)

    def test_microphone_help_mentions_audio_group(self):
        help_lines = LinuxPlatform().get_microphone_permission_help()
        assert any("audio" in line.lower() for line in help_lines)

    def test_general_permission_help_includes_clipboard(self):
        with patch.dict("os.environ", {"WAYLAND_DISPLAY": ""}, clear=False):
            help_lines = LinuxPlatform().get_permission_help()
        assert any("clipboard" in line.lower() or "xclip" in line.lower() for line in help_lines)


class TestLinuxGlobalKeyAccess:
    def test_x11_session_has_access(self):
        with patch.dict("os.environ", {"WAYLAND_DISPLAY": "", "XDG_SESSION_TYPE": "x11"}, clear=False):
            assert LinuxPlatform().has_global_key_access() is True

    def test_wayland_session_has_no_access(self):
        with patch.dict("os.environ", {"WAYLAND_DISPLAY": "wayland-0"}, clear=False):
            assert LinuxPlatform().has_global_key_access() is False
