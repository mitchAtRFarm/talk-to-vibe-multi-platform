import os
import stat
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _read(filename: str) -> str:
    return (REPO_ROOT / filename).read_text()


def _is_executable(path: Path) -> bool:
    mode = path.stat().st_mode
    return bool(mode & stat.S_IXUSR)


def test_setup_linux_script_exists_and_executable():
    script = REPO_ROOT / "setup_linux.sh"
    assert script.exists()
    assert _is_executable(script)


def test_setup_linux_installs_required_apt_packages():
    content = _read("setup_linux.sh")
    for pkg in (
        "libportaudio2",
        "xclip",
        "libayatana-appindicator3-1",
        "gir1.2-ayatanaappindicator3-0.1",
        "python3-gi",
        "libnotify-bin",
    ):
        assert pkg in content, f"setup_linux.sh missing apt package {pkg}"


def test_setup_linux_creates_venv_with_system_site_packages():
    content = _read("setup_linux.sh")
    assert "--system-site-packages" in content


def test_setup_linux_writes_desktop_entry():
    content = _read("setup_linux.sh")
    assert ".local/share/applications" in content
    assert "[Desktop Entry]" in content


def test_setup_linux_offers_autostart():
    content = _read("setup_linux.sh")
    assert "autostart" in content.lower()
    assert ".config/autostart" in content


def test_setup_linux_warns_on_wayland():
    content = _read("setup_linux.sh")
    assert "Wayland" in content
    assert "X11" in content


def test_setup_linux_invokes_whisper_installer_for_local_whisper():
    content = _read("setup_linux.sh")
    assert "maybe_install_whisper" in content
    assert "linux_install_and_set_whisper.sh" in content
    assert "--skip-config" in content
    assert 'import faster_whisper' in content


def test_setup_linux_wizard_does_not_launch_app():
    content = _read("setup_linux.sh")
    assert "python -m talk_to_vibe --setup" not in content
    assert '"$VENV_DIR/bin/python" -m talk_to_vibe --setup' not in content
    assert "from talk_to_vibe.config.wizard import run_wizard" in content


def test_uninstall_linux_script_exists_and_executable():
    script = REPO_ROOT / "uninstall_linux.sh"
    assert script.exists()
    assert _is_executable(script)


def test_uninstall_linux_removes_launcher_and_desktop_entry():
    content = _read("uninstall_linux.sh")
    assert "rm -f \"$LAUNCHER\"" in content
    assert "rm -f \"$DESKTOP_FILE\"" in content
    assert "rm -f \"$AUTOSTART_FILE\"" in content


def test_uninstall_linux_supports_keep_config():
    content = _read("uninstall_linux.sh")
    assert "--keep-config" in content


def test_run_ttv_works_on_linux():
    content = _read("run_ttv.sh")
    assert "talk_to_vibe" in content
