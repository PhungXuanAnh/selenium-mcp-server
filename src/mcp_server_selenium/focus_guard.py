"""Keep the controlled Chrome window from taking desktop focus away from the user.

Headful Chrome activates its OS window for some automation commands no matter which
DevTools client sends them: tab activation (switch/new/close window), trusted mouse
presses, and WebDriver screenshots. Tools avoid those commands where CDP offers a
non-activating equivalent; this guard covers the rest on X11 by returning focus to the
window the user had before the command, if Chrome took it.
"""

import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, Optional

from selenium import webdriver
from selenium.webdriver.remote.command import Command

logger = logging.getLogger(__name__)

# Chrome can raise its window up to about a second after the command returns.
SETTLE_SECONDS = 2.0
POLL_SECONDS = 0.05

ACTIVATING_COMMANDS = frozenset(
    {
        Command.SWITCH_TO_WINDOW,
        Command.NEW_WINDOW,
        Command.CLOSE,
        Command.CLICK_ELEMENT,
        Command.W3C_ACTIONS,
        Command.SCREENSHOT,
        Command.ELEMENT_SCREENSHOT,
    }
)
ACTIVATING_CDP_METHODS = frozenset(
    {
        "Target.activateTarget",
        "Target.createTarget",
        "Page.bringToFront",
        "Input.dispatchMouseEvent",
        "Input.dispatchTouchEvent",
        "Input.synthesizeTapGesture",
    }
)


class FocusGuard:
    """Return X11 focus to the user's window when our Chrome steals it."""

    def __init__(self, user_data_dir: Callable[[], str]) -> None:
        self._user_data_dir = user_data_dir
        self._xdotool = self._find_xdotool()
        self._lock = threading.Lock()
        self._active_calls = 0
        self._deadline = 0.0
        self._user_window = ""
        self._watcher: Optional[threading.Thread] = None
        self._owners: dict[str, bool] = {}

    @staticmethod
    def _find_xdotool() -> str:
        if not sys.platform.startswith("linux") or not os.environ.get("DISPLAY"):
            return ""
        if os.environ.get("SELENIUM_MCP_ALLOW_FOCUS_STEAL") == "1":
            return ""
        path = shutil.which("xdotool") or ""
        if not path:
            logger.info("xdotool not found; Chrome window focus guard is disabled")
        return path

    @property
    def enabled(self) -> bool:
        return bool(self._xdotool)

    def _xdotool_output(self, *arguments: str) -> str:
        try:
            result = subprocess.run(
                [self._xdotool, *arguments],
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        return result.stdout.strip() if result.returncode == 0 else ""

    def _is_browser_window(self, window: str) -> bool:
        if window not in self._owners:
            pid = self._xdotool_output("getwindowpid", window)
            try:
                command = Path(f"/proc/{pid}/cmdline").read_bytes() if pid else b""
            except OSError:
                command = b""
            marker = f" --user-data-dir={self._user_data_dir()} ".encode()
            # Chrome rewrites argv into one space-separated process title.
            self._owners[window] = marker in b" " + command.replace(b"\0", b" ") + b" "
        return self._owners[window]

    @contextmanager
    def protect(self) -> Iterator[None]:
        """Guard one browser command plus the settle period after it."""
        if not self.enabled:
            yield
            return
        with self._lock:
            idle = self._active_calls == 0 and time.monotonic() >= self._deadline
            if idle:
                # A window captured mid-guard may be Chrome's own pending activation.
                window = self._xdotool_output("getactivewindow")
                self._user_window = (
                    "" if not window or self._is_browser_window(window) else window
                )
            self._active_calls += 1
            if self._user_window and self._watcher is None:
                self._watcher = threading.Thread(
                    target=self._watch, name="selenium-focus-guard", daemon=True
                )
                self._watcher.start()
        try:
            yield
        finally:
            with self._lock:
                self._active_calls -= 1
                self._deadline = time.monotonic() + SETTLE_SECONDS

    def _watch(self) -> None:
        while True:
            with self._lock:
                if self._active_calls == 0 and time.monotonic() >= self._deadline:
                    self._watcher = None
                    return
                user_window = self._user_window
            window = self._xdotool_output("getactivewindow")
            if window and window != user_window and self._is_browser_window(window):
                logger.info("Chrome took desktop focus; returning it to window %s", user_window)
                self._xdotool_output("windowactivate", user_window)
            time.sleep(POLL_SECONDS)


class FocusGuardedChrome(webdriver.Chrome):
    """Chrome WebDriver whose window-activating commands run under a FocusGuard."""

    focus_guard: Optional[FocusGuard] = None

    def execute(self, driver_command: str, params: Optional[dict] = None) -> dict:
        activating = driver_command in ACTIVATING_COMMANDS or (
            driver_command == "executeCdpCommand"
            and (params or {}).get("cmd") in ACTIVATING_CDP_METHODS
        )
        if activating and self.focus_guard is not None:
            with self.focus_guard.protect():
                return super().execute(driver_command, params)
        return super().execute(driver_command, params)
