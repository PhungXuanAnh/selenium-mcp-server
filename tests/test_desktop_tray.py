import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp_server_selenium import desktop_tray
from mcp_server_selenium.desktop_tray.native import PROJECT_FILE


class PrepareChromeEnvTest(unittest.TestCase):
    def test_preloads_helper_records_project_and_keeps_preferences(self) -> None:
        with tempfile.TemporaryDirectory() as user_data_dir:
            preferences = Path(user_data_dir) / "Default" / "Preferences"
            preferences.parent.mkdir()
            preferences.write_text(json.dumps({"browser": {"window_placement": {"top": 1}}}))
            with patch.object(desktop_tray, "library_path", return_value=Path("/cache/tray.so")):
                env = desktop_tray.prepare_chrome_env(
                    {"DISPLAY": ":0", "LD_PRELOAD": "/other.so"},
                    user_data_dir,
                    "Default",
                    Path("/work/shop"),
                )

            self.assertEqual("/cache/tray.so:/other.so", env["LD_PRELOAD"])
            self.assertEqual("/work/shop", (Path(user_data_dir) / PROJECT_FILE).read_text())
            browser = json.loads(preferences.read_text())["browser"]
            self.assertEqual({"window_placement": {"top": 1}, "custom_chrome_frame": False}, browser)


if __name__ == "__main__":
    unittest.main()
