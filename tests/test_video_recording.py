import base64
import io
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from mcp_server_selenium.tools.video_recording import (
    DevToolsCommandError,
    FollowActiveRecordingManager,
    RecordingCoordinator,
    RecordingManager,
)


MP4_BYTES = b"\x00\x00\x00\x18ftypisom" + (b"\x00" * 128)


class FakeDriver:
    current_window_handle = "tab-1"
    window_handles = ["tab-1", "tab-2"]
    current_url = "https://start.test/path"
    capabilities = {
        "browserVersion": "152.0",
        "goog:chromeOptions": {"debuggerAddress": "127.0.0.1:9222"},
    }


class FakeConnection:
    instances = []

    def __init__(self, debugger_address, event_callback):
        self.debugger_address = debugger_address
        self.event_callback = event_callback
        self.read_complete = False
        self.closed = False
        self.commands = []
        self.last_session_id = ""
        self.__class__.instances.append(self)

    def command(self, method, params=None, *, session_id="", timeout=30):
        self.commands.append((method, params or {}, session_id))
        if method == "Target.getTargets":
            return {
                "targetInfos": [
                    {
                        "targetId": "tab-1",
                        "type": "page",
                        "url": "https://start.test/path",
                    },
                    {
                        "targetId": "tab-2",
                        "type": "page",
                        "url": "https://selected.test/path",
                    },
                ]
            }
        if method == "Target.attachToTarget":
            self.last_session_id = f"session-{params['targetId']}"
            return {"sessionId": self.last_session_id}
        if method == "Page.getFrameTree":
            return {"frameTree": {"frame": {"id": "frame-1"}}}
        if method in {"Page.startScreenRecording", "Page.stopScreenRecording"}:
            return {"stream": "stream-1"}
        if method == "IO.read":
            if self.read_complete:
                return {"data": "", "eof": True}
            self.read_complete = True
            return {
                "data": base64.b64encode(MP4_BYTES).decode(),
                "base64Encoded": True,
                "eof": True,
            }
        return {}

    def emit_navigation(self, url):
        self.event_callback(
            {
                "sessionId": self.last_session_id,
                "method": "Page.frameNavigated",
                "params": {"frame": {"id": "frame-1", "url": url}},
            }
        )

    def close(self):
        self.closed = True


class FallbackConnection(FakeConnection):
    def command(self, method, params=None, *, session_id="", timeout=30):
        if method == "Page.startScreenRecording":
            raise DevToolsCommandError(-32601, "method not found")
        result = super().command(
            method,
            params,
            session_id=session_id,
            timeout=timeout,
        )
        if method == "Page.startScreencast":
            self.event_callback(
                {
                    "sessionId": session_id,
                    "method": "Page.screencastFrame",
                    "params": {
                        "data": base64.b64encode(b"jpeg-frame").decode(),
                        "sessionId": 1,
                    },
                }
            )
        return result

    def send_no_wait(self, method, params=None, *, session_id=""):
        self.commands.append((method, params or {}, session_id))


class FakeEncoder:
    def __init__(self, arguments, **kwargs):
        self.output_path = Path(arguments[-1])
        self.stdin = io.BytesIO()
        self.stderr = io.BytesIO()
        self.return_code = None

    def poll(self):
        return self.return_code

    def wait(self, timeout=None):
        self.output_path.write_bytes(MP4_BYTES)
        self.return_code = 0
        return 0

    def terminate(self):
        self.return_code = -15

    def kill(self):
        self.return_code = -9


class FakeTimer:
    instances = []

    def __init__(self, interval, callback, args=()):
        self.interval = interval
        self.callback = callback
        self.args = args
        self.cancelled = False
        self.daemon = False
        self.__class__.instances.append(self)

    def start(self):
        return None

    def cancel(self):
        self.cancelled = True

    def fire(self):
        if not self.cancelled:
            self.callback(*self.args)


class VideoRecordingTests(unittest.TestCase):
    def setUp(self):
        FakeConnection.instances.clear()
        FakeTimer.instances.clear()

    @patch("mcp_server_selenium.tools.screenshot.get_workspace_root")
    def test_lifecycle_uses_screenshot_style_paths(self, get_workspace_root):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            get_workspace_root.return_value = workspace
            manager = RecordingManager(
                connection_factory=FakeConnection,
                timer_factory=FakeTimer,
            )

            driver = FakeDriver()
            started = manager.start(
                driver,
                "checkout.MP4",
                "evidence/video",
                window_handle="tab-2",
                max_duration_seconds=30,
            )
            duplicate = manager.start(FakeDriver(), "other", "evidence/video")
            status = manager.status()
            stopped = manager.stop()
            restarted = manager.start(FakeDriver(), "checkout", "evidence/video")
            shutdown = manager.shutdown()
            auto_started = manager.start(
                FakeDriver(),
                "checkout",
                "evidence/video",
                max_duration_seconds=30,
            )
            FakeTimer.instances[-1].fire()
            after_auto_stop = manager.status()
            invalid = manager.start(
                FakeDriver(), "invalid-duration", max_duration_seconds=0
            )
            coordinator = RecordingCoordinator(
                manager_factory=lambda: RecordingManager(
                    connection_factory=FakeConnection,
                    timer_factory=FakeTimer,
                ),
                flow_factory=lambda: FollowActiveRecordingManager(
                    connection_factory=FallbackConnection,
                    ffmpeg_finder=lambda name: "/usr/bin/ffmpeg",
                    process_factory=FakeEncoder,
                    timer_factory=FakeTimer,
                ),
            )
            group_started = coordinator.start(
                FakeDriver(),
                "parallel",
                "evidence/video",
                window_handles=["tab-1", "tab-2"],
                max_duration_seconds=30,
            )
            group_status = coordinator.status()
            coordinator.notify_active_handle("tab-2")
            coordinator.notify_active_handle("tab-1")
            group_stopped = coordinator.stop()
            auto_group_started = coordinator.start(
                FakeDriver(),
                "parallel-auto",
                "evidence/video",
                window_handles=["tab-1", "tab-2"],
                max_duration_seconds=30,
            )
            FakeTimer.instances[-1].fire()
            auto_group_status = coordinator.status()
            shutdown_group_started = coordinator.start(
                FakeDriver(),
                "parallel-shutdown",
                "evidence/video",
                window_handles=["tab-1", "tab-2"],
            )
            shutdown_group = coordinator.shutdown()
            conflicting = coordinator.start(
                FakeDriver(),
                "conflict",
                window_handle="tab-1",
                window_handles=["tab-2"],
            )

            self.assertTrue(
                started["ok"] and stopped["ok"] and shutdown["ok"]
                and auto_started["ok"]
            )
            self.assertEqual("recording_already_active", duplicate["error"]["code"])
            self.assertEqual("tab-2", status["recording"]["handle"])
            self.assertEqual("https://selected.test/path", started["start_url"])
            self.assertEqual("tab-1", driver.current_window_handle)
            self.assertEqual(30, started["max_duration_seconds"])
            self.assertTrue(started["cleanup_required"])
            self.assertIn("stop", started["next_action"])
            self.assertLessEqual(status["recording"]["remaining_seconds"], 30)
            self.assertTrue(status["recording"]["deadline_at"])
            self.assertEqual("manual_stop", stopped["stop_reason"])
            self.assertEqual("server_shutdown", shutdown["stop_reason"])
            self.assertEqual("idle", after_auto_stop["state"])
            self.assertEqual(
                "max_duration_reached",
                after_auto_stop["last_result"]["stop_reason"],
            )
            self.assertFalse(after_auto_stop["cleanup_required"])
            self.assertEqual("invalid_duration", invalid["error"]["code"])
            self.assertEqual(workspace / "evidence/video/checkout.mp4", Path(stopped["path"]))
            self.assertEqual(
                workspace / "evidence/video/checkout-2.mp4",
                Path(shutdown["path"]),
            )
            self.assertEqual(
                workspace / "evidence/video/checkout-3.mp4",
                Path(after_auto_stop["last_result"]["path"]),
            )
            self.assertTrue(Path(stopped["path"]).read_bytes().startswith(MP4_BYTES[:12]))
            self.assertFalse(any(workspace.rglob("*.part")))
            self.assertTrue(restarted["ok"])
            self.assertTrue(group_started["ok"] and group_stopped["ok"])
            self.assertTrue(auto_group_started["ok"] and shutdown_group_started["ok"])
            self.assertEqual("follow_active", group_status["recording"]["mode"])
            self.assertEqual(
                ["tab-1", "tab-2"],
                group_status["recording"]["handles"],
            )
            self.assertEqual(
                "parallel.mp4",
                Path(group_stopped["path"]).name,
            )
            self.assertTrue(Path(group_stopped["path"]).is_file())
            self.assertEqual(2, group_stopped["switch_count"])
            self.assertEqual("idle", auto_group_status["state"])
            self.assertEqual(
                "max_duration_reached",
                auto_group_status["last_result"]["stop_reason"],
            )
            self.assertEqual(
                "server_shutdown",
                shutdown_group["stop_reason"],
            )
            self.assertEqual(
                "conflicting_tab_selection", conflicting["error"]["code"]
            )

    def test_include_address_composites_and_cleans_temporary_files(self):
        commands = []

        def run_ffmpeg(arguments, **kwargs):
            commands.append(arguments)
            Path(arguments[-1]).write_bytes(MP4_BYTES)
            return SimpleNamespace(returncode=0, stderr="", stdout="")

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = RecordingManager(
                connection_factory=FallbackConnection,
                ffmpeg_finder=lambda name: "/usr/bin/ffmpeg",
                process_runner=run_ffmpeg,
                process_factory=FakeEncoder,
                timer_factory=FakeTimer,
            )
            started = manager.start(
                FakeDriver(),
                "address-visible",
                temp_dir,
                include_address=True,
            )
            FakeConnection.instances[-1].emit_navigation("https://next.test/page")
            stopped = manager.stop()
            flow = FollowActiveRecordingManager(
                connection_factory=FallbackConnection,
                ffmpeg_finder=lambda name: "/usr/bin/ffmpeg",
                process_runner=run_ffmpeg,
                process_factory=FakeEncoder,
                timer_factory=FakeTimer,
            )
            flow_started = flow.start(
                FakeDriver(),
                "address-flow",
                temp_dir,
                True,
                ["tab-1", "tab-2"],
                30,
            )
            flow.notify_active_handle("tab-2")
            flow_stopped = flow.stop()

            self.assertTrue(
                started["ok"] and stopped["ok"]
                and flow_started["ok"] and flow_stopped["ok"]
            )
            self.assertEqual("screencast", stopped["transport"])
            self.assertTrue(stopped["include_address"])
            self.assertIn("pad=iw:ih+64", commands[0][commands[0].index("-vf") + 1])
            self.assertTrue(Path(stopped["path"]).is_file())
            self.assertEqual("address-flow.mp4", Path(flow_stopped["path"]).name)
            self.assertEqual(1, flow_stopped["switch_count"])
            self.assertTrue(flow_stopped["include_address"])
            self.assertFalse(list(Path(temp_dir).glob(".*.part")))
            self.assertFalse(list(Path(temp_dir).glob("*.ass")))
            self.assertTrue(
                any(
                    command[0] == "Page.screencastFrameAck"
                    for command in FakeConnection.instances[-1].commands
                )
            )


if __name__ == "__main__":
    unittest.main()
