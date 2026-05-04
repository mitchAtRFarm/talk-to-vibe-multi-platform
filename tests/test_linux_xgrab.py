from unittest.mock import patch

from talk_to_vibe.platforms.linux_xgrab import XChordGrabber, chord_components


class TestChordComponents:
    def test_ctrl_plus_digit(self):
        mods, primary = chord_components("ctrl+9")
        assert mods == ["ctrl"]
        assert primary == "9"

    def test_three_part_chord(self):
        mods, primary = chord_components("ctrl+alt_r+f18")
        assert "ctrl" in mods and "alt_r" in mods
        assert primary == "f18"

    def test_modifier_only_chord(self):
        mods, primary = chord_components("alt_r")
        assert mods == ["alt_r"]
        assert primary is None

    def test_uppercase_normalized(self):
        mods, primary = chord_components("Ctrl+F19")
        assert mods == ["ctrl"]
        assert primary == "f19"


class TestXChordGrabber:
    def test_modifier_only_chord_does_not_grab(self):
        grabber = XChordGrabber("alt_r")
        with patch("Xlib.display.Display") as mock_display:
            assert grabber.start() is False
            mock_display.assert_not_called()

    def test_unknown_primary_key_skips_grab(self):
        grabber = XChordGrabber("ctrl+nonsense")
        with patch("Xlib.display.Display") as mock_display:
            assert grabber.start() is False
            mock_display.assert_not_called()

    def test_failed_display_open_returns_false(self):
        grabber = XChordGrabber("ctrl+9")
        with patch("Xlib.display.Display", side_effect=RuntimeError("no display")):
            assert grabber.start() is False
        assert grabber._thread is None
