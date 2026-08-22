import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from mcp_server_selenium.tools.screenshot import take_screenshot
from mcp_server_selenium.tools.tabs import close_tab, list_tabs, open_tab, switch_tab


class FakeSwitchTo:
    def __init__(self, driver):
        self.driver = driver

    def window(self, handle):
        if handle not in self.driver.handles:
            raise ValueError(handle)
        self.driver.active_handle = handle

    def new_window(self, window_type):
        handle = f"tab-{len(self.driver.handles) + 1}"
        self.driver.handles.append(handle)
        self.driver.pages[handle] = {"title": "", "url": "about:blank"}
        self.driver.active_handle = handle


class FakeDriver:
    def __init__(self):
        self.handles = ["tab-1"]
        self.active_handle = "tab-1"
        self.pages = {"tab-1": {"title": "First", "url": "https://first.test"}}
        self.switch_to = FakeSwitchTo(self)

    @property
    def window_handles(self):
        return list(self.handles)

    @property
    def current_window_handle(self):
        return self.active_handle

    @property
    def title(self):
        return self.pages[self.active_handle]["title"]

    @property
    def current_url(self):
        return self.pages[self.active_handle]["url"]

    def get(self, url):
        self.pages[self.active_handle]["url"] = url

    def close(self):
        self.handles.remove(self.active_handle)


class TabAndScreenshotTests(unittest.TestCase):
    @patch("mcp_server_selenium.tools.tabs.ensure_driver_initialized")
    def test_tab_lifecycle(self, ensure_driver_initialized):
        driver = FakeDriver()
        ensure_driver_initialized.return_value = driver

        opened = json.loads(open_tab("second.test"))
        listed = json.loads(list_tabs())
        switched = json.loads(switch_tab("tab-1"))
        switch_tab(opened["handle"])
        closed = json.loads(close_tab())

        self.assertEqual("https://second.test", opened["url"])
        self.assertEqual(2, len(listed["tabs"]))
        self.assertEqual("tab-1", switched["handle"])
        self.assertEqual(["tab-1"], closed["remaining_handles"])
        self.assertEqual("tab-1", driver.current_window_handle)

    @patch("mcp_server_selenium.tools.screenshot.ensure_driver_initialized")
    def test_exact_and_default_screenshot_paths(self, ensure_driver_initialized):
        driver = Mock()
        ensure_driver_initialized.return_value = driver

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "nested" / "shot.png"
            take_screenshot(str(target))
            take_screenshot()

            exact_path = Path(driver.save_screenshot.call_args_list[0].args[0])
            default_path = Path(driver.save_screenshot.call_args_list[1].args[0])
            self.assertEqual(target, exact_path)
            self.assertTrue(target.parent.is_dir())
            self.assertFalse(target.is_dir())
            self.assertEqual(Path.cwd(), default_path.parent)
            self.assertTrue(default_path.name.startswith("screenshot_"))


if __name__ == "__main__":
    unittest.main()
