import os
import sys
import types

import pytest


def _ensure_sounddevice_importable():
    try:
        import sounddevice  # noqa: F401
        return
    except OSError:
        pass

    fake = types.ModuleType("sounddevice")

    class PortAudioError(Exception):
        pass

    class _InputStream:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            pass

        def stop(self):
            pass

        def close(self):
            pass

    def query_devices():
        return []

    fake.PortAudioError = PortAudioError
    fake.InputStream = _InputStream
    fake.query_devices = query_devices
    sys.modules["sounddevice"] = fake


_ensure_sounddevice_importable()


@pytest.fixture(scope="session", autouse=True)
def isolate_app_log_path(tmp_path_factory):
    log_path = tmp_path_factory.mktemp("logs") / "test-app.log"
    original = os.environ.get("TALKTOVIBE_LOG_PATH")
    os.environ["TALKTOVIBE_LOG_PATH"] = str(log_path)
    try:
        yield
    finally:
        if original is None:
            os.environ.pop("TALKTOVIBE_LOG_PATH", None)
        else:
            os.environ["TALKTOVIBE_LOG_PATH"] = original
