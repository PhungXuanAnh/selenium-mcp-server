"""Close controlled Chrome to one shared Selenium MCP tray icon on Linux X11."""

import json
import subprocess
from pathlib import Path

from .native import CACHE_DIRECTORY, PROJECT_FILE, TrayUnavailable, library_path

DAEMON = Path(__file__).with_name("daemon.py")
# The daemon needs GTK and AyatanaAppIndicator3 from the distribution's Python.
SYSTEM_PYTHON = Path("/usr/bin/python3")
# The helper hooks XCB, so Chrome must use X11 even inside a Wayland session.
CHROME_ARGUMENTS = ["--ozone-platform=x11"]
# The server's virtualenv settings must not leak into the system Python.
DAEMON_UNSET = {"LD_PRELOAD", "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}

__all__ = ["CHROME_ARGUMENTS", "TrayUnavailable", "prepare_chrome_env", "start_daemon"]


def _use_system_title_bar(user_data_dir: str, profile: str) -> None:
    """Chrome's own title-bar X never sends the X11 close request the helper intercepts."""
    preferences_path = Path(user_data_dir) / profile / "Preferences"
    preferences = {}
    if preferences_path.exists():
        preferences = json.loads(preferences_path.read_text(encoding="utf-8"))
    preferences.setdefault("browser", {})["custom_chrome_frame"] = False
    preferences_path.parent.mkdir(parents=True, exist_ok=True)
    preferences_path.write_text(json.dumps(preferences), encoding="utf-8")


def prepare_chrome_env(env: dict, user_data_dir: str, profile: str, project: Path) -> dict:
    """Return the launch environment that makes Chrome's window close hide it to the tray."""
    if not env.get("DISPLAY"):
        raise TrayUnavailable("an X11 DISPLAY is required")
    library = library_path()
    _use_system_title_bar(user_data_dir, profile)
    (Path(user_data_dir) / PROJECT_FILE).write_text(str(project), encoding="utf-8")
    preload = [str(library), env.get("LD_PRELOAD", "")]
    return {**env, "LD_PRELOAD": ":".join(item for item in preload if item)}


def start_daemon(env: dict) -> None:
    """Start the shared tray icon; a second daemon exits at once on the held lock."""
    if not SYSTEM_PYTHON.exists():
        raise TrayUnavailable(f"{SYSTEM_PYTHON} with python3-gi is required for the tray icon")
    CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    daemon_env = {key: value for key, value in env.items() if key not in DAEMON_UNSET}
    with open(CACHE_DIRECTORY / "tray-daemon.log", "ab") as log:
        subprocess.Popen(
            [str(SYSTEM_PYTHON), str(DAEMON)],
            cwd=DAEMON.parent,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            env=daemon_env,
            start_new_session=True,
        )
