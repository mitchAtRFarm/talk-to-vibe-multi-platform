from unittest.mock import patch

from talk_to_vibe.audio.recorder import AudioRecorder


class TestAudioRecorder:
    def test_start_reports_error_via_callback(self):
        errors = []

        with patch("talk_to_vibe.audio.recorder.find_real_microphone", return_value=(None, "system default")), \
             patch("talk_to_vibe.audio.recorder.sd.InputStream", side_effect=__import__("sounddevice").PortAudioError("denied")):
            recorder = AudioRecorder(error_callback=errors.append)
            assert recorder.start() is False

        assert len(errors) == 1
        assert "Microphone error" in errors[0]

    def test_start_without_callback_prints_message(self, capsys):
        with patch("talk_to_vibe.audio.recorder.find_real_microphone", return_value=(None, "system default")), \
             patch("talk_to_vibe.audio.recorder.sd.InputStream", side_effect=__import__("sounddevice").PortAudioError("denied")):
            recorder = AudioRecorder()
            assert recorder.start() is False

        captured = capsys.readouterr()
        assert "Microphone error" in captured.out
