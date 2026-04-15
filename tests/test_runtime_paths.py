import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from talk_to_vibe.runtime_paths import (
    APP_BUNDLE_NAME,
    APP_LOG_BACKUP_COUNT,
    APP_LOG_MAX_BYTES,
    APP_NAME,
    CONFIGURE_HELPER_NAME,
    InstallManifest,
    build_launch_agent_plist,
    configure_file_logging,
    load_install_manifest,
    write_install_manifest,
)


class TestInstallManifest:
    def test_roundtrip_manifest(self, tmp_path):
        manifest_path = tmp_path / "install-manifest.yaml"
        original = InstallManifest(
            app_path="/tmp/TalkToVibe.app",
            helper_path="/tmp/talktovibe-configure",
            launch_at_login=True,
            brew_packages=["portaudio"],
            install_version="1.2.3",
        )

        write_install_manifest(original, path=manifest_path)
        loaded = load_install_manifest(path=manifest_path)

        assert loaded == original

    def test_missing_manifest_returns_none(self, tmp_path):
        assert load_install_manifest(path=tmp_path / "missing.yaml") is None


class TestLaunchAgentPlist:
    def test_contains_bundle_label_and_app_path(self, tmp_path):
        app_path = tmp_path / APP_BUNDLE_NAME
        plist = build_launch_agent_plist(app_path)
        assert "com.talktovibe.app" in plist
        assert str(app_path) in plist
        assert "/usr/bin/open" in plist


class TestConstants:
    def test_expected_public_names(self):
        assert APP_NAME == "TalkToVibe"
        assert APP_BUNDLE_NAME == "TalkToVibe.app"
        assert CONFIGURE_HELPER_NAME == "talktovibe-configure"


class TestLogging:
    def test_configure_file_logging_uses_rotating_handler(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TALKTOVIBE_LOG_PATH", str(tmp_path / "test.log"))
        logger = configure_file_logging("test.runtime_paths.rotating")
        matching_handlers = [
            handler
            for handler in logger.handlers
            if isinstance(handler, RotatingFileHandler)
        ]

        assert matching_handlers
        handler = matching_handlers[-1]
        assert handler.maxBytes == APP_LOG_MAX_BYTES
        assert handler.backupCount == APP_LOG_BACKUP_COUNT

    def test_configure_file_logging_does_not_add_duplicate_handlers(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TALKTOVIBE_LOG_PATH", str(tmp_path / "test.log"))
        logger_name = "test.runtime_paths.no_duplicates"
        logger = configure_file_logging(logger_name)
        initial_handler_count = len(logger.handlers)

        configure_file_logging(logger_name)

        assert len(logger.handlers) == initial_handler_count

    def test_configure_file_logging_respects_env_override(self, monkeypatch, tmp_path):
        override_path = tmp_path / "override.log"
        monkeypatch.setenv("TALKTOVIBE_LOG_PATH", str(override_path))
        logger = configure_file_logging("test.runtime_paths.override")
        handler = next(handler for handler in logger.handlers if isinstance(handler, RotatingFileHandler))
        assert Path(handler.baseFilename) == override_path
