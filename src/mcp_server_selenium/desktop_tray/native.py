"""Build and call the X11 close-to-tray helper of the controlled Chrome.

Standard library only: the tray daemon imports this module under the system Python.
"""

import ctypes
import hashlib
import os
import platform
import re
import shutil
import signal
import subprocess
from pathlib import Path
from typing import List, NamedTuple

SOURCE = Path(__file__).with_name("chrome_tray.c")
CACHE_DIRECTORY = (
    Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "selenium-mcp-server"
)
# Written into the Chrome user data dir; Chrome overwrites its own /proc environ.
PROJECT_FILE = ".selenium_mcp_project"
LIBRARY_PREFIX = "chrome-tray-"
# MCP clients may omit or override XDG directories; the per-user lock must stay shared.
DAEMON_LOCK = Path.home() / ".cache" / "selenium-mcp-server" / "selenium-mcp-tray.lock"
MAX_HIDDEN_WINDOWS = 256


class TrayUnavailable(RuntimeError):
    """The desktop cannot run the close-to-tray helper."""


class HiddenWindow(NamedTuple):
    window: int
    pid: int
    title: str


class TrayChrome(NamedTuple):
    pid: int
    project: str
    user_data_dir: str


def library_path() -> Path:
    """Return the compiled helper, building it once per source version and architecture."""
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()[:20]
    path = CACHE_DIRECTORY / f"{LIBRARY_PREFIX}{platform.machine()}-{digest}.so"
    # The dynamic loader splits LD_PRELOAD on colons and whitespace.
    if re.search(r"[:\s]", str(path)):
        raise TrayUnavailable(f"helper path must not contain spaces or colons: {path}")
    if path.exists():
        return path
    compiler = shutil.which("cc")
    if not compiler:
        raise TrayUnavailable("building the helper requires build-essential and libxcb1-dev")
    CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    build = subprocess.run(
        [compiler, "-std=c11", "-shared", "-fPIC", "-fvisibility=hidden", "-O2",
         "-Wall", "-Wextra", str(SOURCE), "-o", str(temporary), "-lxcb", "-ldl"],
        capture_output=True,
        text=True,
    )
    if build.returncode != 0:
        temporary.unlink(missing_ok=True)
        raise TrayUnavailable(
            "helper did not compile; install build-essential and libxcb1-dev. "
            + build.stderr[-2000:]
        )
    temporary.replace(path)
    return path


class Desktop:
    """List, restore and close controlled Chrome windows on the X11 display."""

    def __init__(self) -> None:
        library = ctypes.CDLL(str(library_path()))
        self._hidden_windows = library.selenium_mcp_hidden_windows
        self._hidden_windows.argtypes = [
            ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32), ctypes.c_int,
        ]
        self._window_title = library.selenium_mcp_window_title
        self._window_title.argtypes = [ctypes.c_uint32, ctypes.c_char_p, ctypes.c_int]
        self._restore = library.selenium_mcp_restore
        self._restore.argtypes = [ctypes.c_uint32]
        self._request_close = library.selenium_mcp_request_close
        self._request_close.argtypes = [ctypes.c_uint32]

    @staticmethod
    def _checked(status: int) -> int:
        if status < 0:
            raise TrayUnavailable("cannot connect to the X11 display")
        return status

    def hidden_windows(self) -> List[HiddenWindow]:
        windows = (ctypes.c_uint32 * MAX_HIDDEN_WINDOWS)()
        pids = (ctypes.c_uint32 * MAX_HIDDEN_WINDOWS)()
        count = self._checked(self._hidden_windows(windows, pids, MAX_HIDDEN_WINDOWS))
        hidden = []
        for index in range(count):
            title = ctypes.create_string_buffer(1024)
            self._checked(self._window_title(windows[index], title, len(title)))
            hidden.append(
                HiddenWindow(windows[index], pids[index], title.value.decode("utf-8", "replace"))
            )
        return hidden

    def restore(self, window: int) -> bool:
        return self._checked(self._restore(window)) == 1

    def restore_profile(self, user_data_dir: str) -> None:
        """Show hidden windows belonging to the profile being connected."""
        profile_path = Path(user_data_dir).resolve()
        pids = {
            chrome.pid for chrome in tray_chromes()
            if Path(chrome.user_data_dir).resolve() == profile_path
        }
        for window in self.hidden_windows():
            if window.pid in pids:
                self.restore(window.window)

    def request_close(self, window: int) -> None:
        """Close a window the way its title-bar X button does."""
        self._checked(self._request_close(window))


def close_chrome(pid: int) -> None:
    """Quit one project's Chrome for good, the way its menu's Exit does."""
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


def tray_chromes() -> List[TrayChrome]:
    """Return running Chrome browser processes that loaded the close-to-tray helper."""
    chromes = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            # Browser updates unlink the old executable while Chrome keeps running.
            executable = os.readlink(entry / "exe").removesuffix(" (deleted)")
            if Path(executable).name != "chrome":
                continue
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode()
            # Renderer, GPU and utility processes inherit the helper but carry --type=.
            if "--type=" in command or str(CACHE_DIRECTORY / LIBRARY_PREFIX) not in (entry / "maps").read_text():
                continue
        except OSError:
            continue
        user_data_dir = ""
        # Chrome rewrites argv into one space-separated process title.
        for word in command.split():
            if word.startswith("--user-data-dir="):
                user_data_dir = word.partition("=")[2]
        try:
            project = (Path(user_data_dir) / PROJECT_FILE).read_text(encoding="utf-8").strip()
        except OSError:
            project = user_data_dir
        chromes.append(TrayChrome(int(entry.name), project, user_data_dir))
    return chromes
