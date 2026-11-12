import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

from mcp_server_selenium import desktop_tray
from mcp_server_selenium.desktop_tray import native
from mcp_server_selenium.desktop_tray.native import PROJECT_FILE


class PrepareChromeEnvTest(unittest.TestCase):
    def test_restore_keeps_other_profiles_hidden(self) -> None:
        desktop = object.__new__(native.Desktop)
        chromes = [
            native.TrayChrome(123, "/work/shop", "/profiles/shop"),
            native.TrayChrome(456, "/work/other", "/profiles/other"),
        ]
        windows = [native.HiddenWindow(1, 123, "Shop"), native.HiddenWindow(2, 456, "Other")]
        with (
            patch.object(native, "tray_chromes", return_value=chromes),
            patch.object(desktop, "hidden_windows", return_value=windows),
            patch.object(desktop, "restore") as restore,
        ):
            desktop.restore_profile("/profiles/shop")
        self.assertEqual([call(1)], restore.call_args_list)

    def test_tray_launch_recovers_missing_session_bus_and_preserves_explicit_bus(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for address in (None, "unix:path=/custom/session-bus"):
                with self.subTest(address=address):
                    environment = {"DISPLAY": ":0"}
                    if address:
                        environment["DBUS_SESSION_BUS_ADDRESS"] = address
                    with (
                        patch.object(desktop_tray, "CACHE_DIRECTORY", Path(directory)),
                        patch.object(Path, "is_socket", return_value=True),
                        patch.object(desktop_tray.subprocess, "Popen") as launch,
                    ):
                        desktop_tray.start_daemon(environment)
                    self.assertEqual(
                        address or f"unix:path=/run/user/{os.getuid()}/bus",
                        launch.call_args.kwargs["env"].get("DBUS_SESSION_BUS_ADDRESS"),
                    )

    def test_detects_chrome_after_its_executable_is_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            process = Path(directory) / "123"
            process.mkdir()
            profile = Path(directory) / "profile"
            profile.mkdir()
            (profile / PROJECT_FILE).write_text("/work/shop")
            (process / "cmdline").write_bytes(f"chrome\0--user-data-dir={profile}\0".encode())
            (process / "maps").write_text(str(native.CACHE_DIRECTORY / "chrome-tray-test.so"))
            for executable in ("chrome", "chrome (deleted)"):
                with self.subTest(executable=executable):
                    link = process / "exe"
                    link.symlink_to(f"/opt/google/chrome/{executable}")
                    with patch.object(Path, "iterdir", return_value=iter([process])):
                        self.assertEqual(
                            [native.TrayChrome(123, "/work/shop", str(profile))],
                            native.tray_chromes(),
                        )
                    link.unlink()

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
