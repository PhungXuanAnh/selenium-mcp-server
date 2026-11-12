"""One shared Selenium MCP tray icon for every project's controlled Chrome.

Run as a script by the system Python, which provides GTK and AyatanaAppIndicator3. The
menu lists hidden Chrome windows by project and closes a project's Chrome for good.
"""

import fcntl
import signal
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3 as AppIndicator  # noqa: E402
from gi.repository import GLib, Gtk  # noqa: E402

from native import DAEMON_LOCK, Desktop, close_chrome, tray_chromes  # noqa: E402

ICON = Path(__file__).with_name("icon.svg")
REFRESH_SECONDS = 1
TITLE_SUFFIX = " - Google Chrome"


def project_name(project: str) -> str:
    return Path(project).name or project


class SeleniumTray:
    def __init__(self, desktop: Desktop) -> None:
        self.desktop = desktop
        self.indicator = AppIndicator.Indicator.new(
            "selenium-mcp-server", str(ICON), AppIndicator.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_title("Selenium MCP")
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.shown_state = None

    def refresh(self) -> bool:
        """Rebuild the menu when it changed; return False once no tray Chrome is running."""
        chromes = tray_chromes()
        if not chromes:
            return False
        projects = {chrome.pid: chrome.project for chrome in chromes}
        hidden = [window for window in self.desktop.hidden_windows() if window.pid in projects]
        state = (hidden, chromes)
        if state != self.shown_state:
            self.indicator.set_menu(self.build_menu(hidden, projects, chromes))
            self.shown_state = state
        return True

    def build_menu(self, hidden, projects, chromes) -> Gtk.Menu:
        menu = Gtk.Menu()
        if not hidden:
            empty = Gtk.MenuItem(label="No hidden Chrome windows")
            empty.set_sensitive(False)
            menu.append(empty)
        for window in hidden:
            title = window.title.removesuffix(TITLE_SUFFIX)
            item = Gtk.MenuItem(label=f"{project_name(projects[window.pid])}: {title}")
            item.connect("activate", self.on_restore, window.window)
            menu.append(item)
        menu.append(Gtk.SeparatorMenuItem())
        close_item = Gtk.MenuItem(label="Close Chrome for good")
        close_menu = Gtk.Menu()
        for chrome in chromes:
            item = Gtk.MenuItem(
                label=f"{project_name(chrome.project)} ({Path(chrome.user_data_dir).name})"
            )
            item.set_tooltip_text(chrome.project)
            item.connect("activate", self.on_close_chrome, chrome.pid)
            close_menu.append(item)
        close_item.set_submenu(close_menu)
        menu.append(close_item)
        menu.show_all()
        return menu

    def on_restore(self, _item, window: int) -> None:
        self.desktop.restore(window)
        self.refresh()

    def on_close_chrome(self, _item, pid: int) -> None:
        close_chrome(pid)
        self.refresh()


def main() -> int:
    DAEMON_LOCK.parent.mkdir(parents=True, exist_ok=True)
    lock = DAEMON_LOCK.open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0
    tray = SeleniumTray(Desktop())
    if not tray.refresh():
        return 0

    def refresh_or_quit() -> bool:
        if tray.refresh():
            return True
        Gtk.main_quit()
        return False

    GLib.timeout_add_seconds(REFRESH_SECONDS, refresh_or_quit)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, Gtk.main_quit)
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
