import os

import pytest


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
