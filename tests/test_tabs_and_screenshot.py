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
        with patch(
            "mcp_server_selenium.tools.tabs.recording_manager.is_recording_handle",
            return_value=True,
        ):
            with self.assertRaisesRegex(ValueError, "record_video"):
                close_tab(opened["handle"])
        closed = json.loads(close_tab())

        self.assertEqual("https://second.test", opened["url"])
        self.assertEqual(2, len(listed["tabs"]))
        self.assertEqual("tab-1", switched["handle"])
        self.assertEqual(["tab-1"], closed["remaining_handles"])
        self.assertEqual("tab-1", driver.current_window_handle)

    @patch("mcp_server_selenium.tools.screenshot.get_workspace_root")
    @patch("mcp_server_selenium.tools.screenshot.ensure_driver_initialized")
    def test_named_screenshot_paths(
        self,
        ensure_driver_initialized,
        get_workspace_root,
    ):
        driver = Mock()
        ensure_driver_initialized.return_value = driver
        driver.save_screenshot.side_effect = lambda path: Path(path).touch()

        with (
            tempfile.TemporaryDirectory() as temp_dir,
            tempfile.TemporaryDirectory() as absolute_temp_dir,
        ):
            workspace_root = Path(temp_dir)
            get_workspace_root.return_value = workspace_root

            take_screenshot("checkout-ready")
            take_screenshot("checkout-ready")
            take_screenshot("details.PNG", "evidence/checkout")
            take_screenshot("external-location", absolute_temp_dir)

            saved_paths = [
                Path(call.args[0]) for call in driver.save_screenshot.call_args_list
            ]
            self.assertEqual(
                [
                    workspace_root / "tmp/selenium-screenshot/checkout-ready.png",
                    workspace_root / "tmp/selenium-screenshot/checkout-ready-2.png",
                    workspace_root / "evidence/checkout/details.png",
                    Path(absolute_temp_dir) / "external-location.png",
                ],
                saved_paths,
            )

    @patch("mcp_server_selenium.tools.screenshot.get_workspace_root")
    @patch("mcp_server_selenium.tools.screenshot.ensure_driver_initialized")
    def test_screenshot_rejects_unsafe_paths(
        self,
        ensure_driver_initialized,
        get_workspace_root,
    ):
        ensure_driver_initialized.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            get_workspace_root.return_value = Path(temp_dir)

            for file_name in ("", "../escape", "nested/shot", "shot.jpg"):
                with self.subTest(file_name=file_name):
                    with self.assertRaises(ValueError):
                        take_screenshot(file_name)

            for directory in ("../outside", "bad\\path"):
                with self.subTest(directory=directory):
                    with self.assertRaises(ValueError):
                        take_screenshot("safe-name", directory)


if __name__ == "__main__":
    unittest.main()
