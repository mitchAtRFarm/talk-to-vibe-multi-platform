from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path

import yaml

APP_NAME = "TalkToVibe"
APP_BUNDLE_NAME = f"{APP_NAME}.app"
APP_BUNDLE_IDENTIFIER = "com.talktovibe.app"
APP_SUPPORT_DIR = Path.home() / ".talktovibe"
APP_BIN_DIR = APP_SUPPORT_DIR / "bin"
APP_LOG_DIR = APP_SUPPORT_DIR / "logs"
APP_LOG_FILE = APP_LOG_DIR / "app.log"
APP_LOG_MAX_BYTES = 1_048_576
APP_LOG_BACKUP_COUNT = 5
INSTALL_MANIFEST_FILE = APP_SUPPORT_DIR / "install-manifest.yaml"
SIGNING_DIR = APP_SUPPORT_DIR / "signing"
SIGNING_KEYCHAIN = SIGNING_DIR / "talktovibe-signing.keychain-db"
SIGNING_CERT_P12 = SIGNING_DIR / "talktovibe-signing.p12"
SIGNING_CERT_PASSWORD_FILE = SIGNING_DIR / "certificate-password.txt"
SIGNING_KEYCHAIN_PASSWORD_FILE = SIGNING_DIR / "keychain-password.txt"
SIGNING_COMMON_NAME = "TalkToVibe Local Dev Signing"
USER_APPLICATIONS_DIR = Path.home() / "Applications"
INSTALLED_APP_PATH = USER_APPLICATIONS_DIR / APP_BUNDLE_NAME
CONFIGURE_HELPER_NAME = "talktovibe-configure"
INSTALLED_CONFIGURE_HELPER_PATH = APP_BIN_DIR / CONFIGURE_HELPER_NAME
LAUNCH_AGENT_LABEL = APP_BUNDLE_IDENTIFIER
LAUNCH_AGENT_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


@dataclass
class InstallManifest:
    app_path: str = str(INSTALLED_APP_PATH)
    helper_path: str = str(INSTALLED_CONFIGURE_HELPER_PATH)
    launch_agent_path: str = str(LAUNCH_AGENT_PATH)
    bundle_identifier: str = APP_BUNDLE_IDENTIFIER
    launch_at_login: bool = False
    brew_packages: list[str] = field(default_factory=list)
    install_version: str = ""


def ensure_app_support_dirs() -> None:
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    APP_BIN_DIR.mkdir(parents=True, exist_ok=True)
    APP_LOG_DIR.mkdir(parents=True, exist_ok=True)
    SIGNING_DIR.mkdir(parents=True, exist_ok=True)


def configure_file_logging(name: str = APP_NAME) -> logging.Logger:
    ensure_app_support_dirs()
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    log_path = os.environ.get("TALKTOVIBE_LOG_PATH", str(APP_LOG_FILE))
    if not any(isinstance(handler, RotatingFileHandler) and getattr(handler, "baseFilename", None) == log_path for handler in logger.handlers):
        handler = RotatingFileHandler(
            log_path,
            maxBytes=APP_LOG_MAX_BYTES,
            backupCount=APP_LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
    return logger


def write_install_manifest(manifest: InstallManifest, path: Path = INSTALL_MANIFEST_FILE) -> None:
    ensure_app_support_dirs()
    path.write_text(yaml.safe_dump(asdict(manifest), sort_keys=False), encoding="utf-8")


def load_install_manifest(path: Path = INSTALL_MANIFEST_FILE) -> InstallManifest | None:
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return None
    known_fields = InstallManifest.__dataclass_fields__
    return InstallManifest(**{key: value for key, value in raw.items() if key in known_fields})


def build_launch_agent_plist(app_path: Path = INSTALLED_APP_PATH) -> str:
    app_path_str = str(app_path)
    return """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\"> 
<plist version=\"1.0\">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/open</string>
    <string>{app_path}</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <false/>
</dict>
</plist>
""".format(label=LAUNCH_AGENT_LABEL, app_path=app_path_str)
