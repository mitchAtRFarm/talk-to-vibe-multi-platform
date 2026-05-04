from unittest.mock import MagicMock, patch

import sounddevice as sd

from talk_to_vibe.audio.recorder import AudioRecorder, find_real_microphone


class TestAudioRecorder:
    def test_start_reports_error_via_callback(self):
        errors = []
        failing_stream = MagicMock()
        failing_stream.start.side_effect = sd.PortAudioError("denied")
        retry_stream = MagicMock()
        retry_stream.start.side_effect = sd.PortAudioError("still denied")

        with patch(
            "talk_to_vibe.audio.recorder.find_real_microphone",
            side_effect=[(1, "Mic A"), (2, "Mic B"), (3, "Mic C")],
        ), patch(
            "talk_to_vibe.audio.recorder.sd.InputStream",
            side_effect=[failing_stream, retry_stream],
        ), patch("talk_to_vibe.audio.recorder.sd._terminate") as mock_terminate, patch(
            "talk_to_vibe.audio.recorder.sd._initialize"
        ) as mock_initialize:
            recorder = AudioRecorder(error_callback=errors.append)
            assert recorder.start() is False

        assert len(errors) == 1
        assert "Microphone error" in errors[0]
        assert "still denied" in errors[0]
        assert "Mic C" in errors[0]
        mock_terminate.assert_called_once_with()
        mock_initialize.assert_called_once_with()

    def test_start_without_callback_prints_message(self, capsys):
        failing_stream = MagicMock()
        failing_stream.start.side_effect = sd.PortAudioError("denied")
        retry_stream = MagicMock()
        retry_stream.start.side_effect = sd.PortAudioError("still denied")

        with patch(
            "talk_to_vibe.audio.recorder.find_real_microphone",
            side_effect=[(1, "Mic A"), (2, "Mic B"), (3, "Mic C")],
        ), patch(
            "talk_to_vibe.audio.recorder.sd.InputStream",
            side_effect=[failing_stream, retry_stream],
        ), patch("talk_to_vibe.audio.recorder.sd._terminate"), patch(
            "talk_to_vibe.audio.recorder.sd._initialize"
        ):
            recorder = AudioRecorder()
            assert recorder.start() is False

        captured = capsys.readouterr()
        assert "Microphone error" in captured.out

    def test_start_re_resolves_device_each_call(self):
        with patch(
            "talk_to_vibe.audio.recorder.find_real_microphone",
            side_effect=[
                (1, "Mic A"),
                (2, "Mic B"),
                (3, "Mic C"),
                (4, "Mic D"),
                (5, "Mic E"),
            ],
        ), patch(
            "talk_to_vibe.audio.recorder.sd.InputStream",
            side_effect=sd.PortAudioError("denied"),
        ):
            recorder = AudioRecorder()
            assert recorder.device_id == 1

            assert recorder.start() is False
            assert recorder.device_id == 3
            assert recorder.device_name == "Mic C"

            assert recorder.start() is False
            assert recorder.device_id == 5
            assert recorder.device_name == "Mic E"

    def test_start_retries_after_backend_reset_and_recovers(self):
        failing_stream = MagicMock()
        failing_stream.start.side_effect = sd.PortAudioError("denied")
        recovered_stream = MagicMock()

        with patch(
            "talk_to_vibe.audio.recorder.find_real_microphone",
            side_effect=[(1, "Mic A"), (2, "Mic B"), (3, "Mic C")],
        ), patch(
            "talk_to_vibe.audio.recorder.sd.InputStream",
            side_effect=[failing_stream, recovered_stream],
        ), patch("talk_to_vibe.audio.recorder.sd._terminate") as mock_terminate, patch(
            "talk_to_vibe.audio.recorder.sd._initialize"
        ) as mock_initialize:
            recorder = AudioRecorder()

            assert recorder.start() is True

        assert recorder.stream is recovered_stream
        assert recorder.device_id == 3
        assert recorder.device_name == "Mic C"
        failing_stream.close.assert_called_once_with()
        recovered_stream.start.assert_called_once_with()
        mock_terminate.assert_called_once_with()
        mock_initialize.assert_called_once_with()

    def test_start_failure_reports_retry_device_and_clears_stream(self):
        failing_stream = MagicMock()
        failing_stream.start.side_effect = sd.PortAudioError("denied")
        retry_stream = MagicMock()
        retry_stream.start.side_effect = sd.PortAudioError("still denied")

        with patch(
            "talk_to_vibe.audio.recorder.find_real_microphone",
            side_effect=[(1, "Mic A"), (2, "Mic B"), (3, "Mic C")],
        ), patch(
            "talk_to_vibe.audio.recorder.sd.InputStream",
            side_effect=[failing_stream, retry_stream],
        ), patch("talk_to_vibe.audio.recorder.sd._terminate") as mock_terminate, patch(
            "talk_to_vibe.audio.recorder.sd._initialize"
        ) as mock_initialize:
            recorder = AudioRecorder()

            assert recorder.start() is False

        assert recorder.stream is None
        assert recorder.device_id == 3
        assert recorder.device_name == "Mic C"
        failing_stream.close.assert_called_once_with()
        retry_stream.close.assert_called_once_with()
        mock_terminate.assert_called_once_with()
        mock_initialize.assert_called_once_with()

    def test_passes_mic_preferences_to_picker(self):
        with patch(
            "talk_to_vibe.audio.recorder.find_real_microphone",
            return_value=(7, "TONOR TC30"),
        ) as picker:
            AudioRecorder(mic_preferences=["TONOR", "NexiGo"])

        assert picker.call_count == 1
        kwargs = picker.call_args.kwargs
        assert kwargs["preferences"] == ["TONOR", "NexiGo"]
        assert kwargs["refresh"] is False


class TestFindRealMicrophone:
    def _devices(self, *names_with_channels):
        return [
            {"name": name, "max_input_channels": ch, "default_samplerate": 44100.0}
            for name, ch in names_with_channels
        ]

    def test_user_preference_wins_over_other_logic(self):
        devices = self._devices(
            ("pipewire", 64),
            ("TONOR TC30 Audio Device: USB Audio (hw:2,0)", 1),
            ("NexiGo N930AF FHD Webcam: USB Audio (hw:3,0)", 1),
        )
        with patch("talk_to_vibe.audio.recorder.sd.query_devices", return_value=devices), \
             patch("talk_to_vibe.audio.recorder._device_accepts_settings", return_value=True), \
             patch("talk_to_vibe.audio.recorder._refresh_portaudio"):
            idx, name = find_real_microphone(preferences=["TONOR"])
        assert idx == 1
        assert "TONOR" in name

    def test_preference_order_is_respected(self):
        devices = self._devices(
            ("Built-in Mic", 1),
            ("TONOR TC30", 1),
            ("NexiGo N930AF", 1),
        )
        with patch("talk_to_vibe.audio.recorder.sd.query_devices", return_value=devices), \
             patch("talk_to_vibe.audio.recorder._device_accepts_settings", return_value=True), \
             patch("talk_to_vibe.audio.recorder._refresh_portaudio"):
            idx, name = find_real_microphone(preferences=["NexiGo", "TONOR"])
        assert idx == 2
        assert "NexiGo" in name

    def test_falls_through_when_preferred_device_disconnected(self):
        devices = self._devices(
            ("sof-hda-dsp: hw:1,0", 2),
            ("pipewire", 64),
            ("default", 64),
        )
        accepts = {0: False, 1: True, 2: True}
        with patch("talk_to_vibe.audio.recorder.sd.query_devices", return_value=devices), \
             patch(
                 "talk_to_vibe.audio.recorder._device_accepts_settings",
                 side_effect=lambda i: accepts.get(i, False),
             ), \
             patch("talk_to_vibe.audio.recorder._refresh_portaudio"):
            idx, name = find_real_microphone(preferences=["TONOR", "NexiGo"])
        assert idx == 1
        assert name == "pipewire"

    def test_skips_devices_that_do_not_accept_sample_rate(self):
        devices = self._devices(
            ("sof-hda-dsp: hw:1,0", 2),
            ("pipewire", 64),
        )
        accepts = {0: False, 1: True}
        with patch("talk_to_vibe.audio.recorder.sd.query_devices", return_value=devices), \
             patch(
                 "talk_to_vibe.audio.recorder._device_accepts_settings",
                 side_effect=lambda i: accepts.get(i, False),
             ), \
             patch("talk_to_vibe.audio.recorder._refresh_portaudio"):
            idx, name = find_real_microphone()
        assert idx == 1
        assert name == "pipewire"

    def test_refreshes_portaudio_when_requested(self):
        with patch("talk_to_vibe.audio.recorder.sd.query_devices", return_value=[]), \
             patch("talk_to_vibe.audio.recorder._device_accepts_settings", return_value=False), \
             patch("talk_to_vibe.audio.recorder._refresh_portaudio") as refresh:
            find_real_microphone(refresh=True)
            assert refresh.call_count == 1
            find_real_microphone(refresh=False)
            assert refresh.call_count == 1
