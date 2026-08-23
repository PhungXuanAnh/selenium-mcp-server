import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from selenium.common.exceptions import ElementClickInterceptedException

from mcp_server_selenium import server
from mcp_server_selenium.tools.compact_diagnostics import (
    DiagnosticsBroker,
    diagnostics_broker,
    response_body,
)
from mcp_server_selenium.tools.compact_locator import LocatorRegistry, locator_registry
from mcp_server_selenium.tools.compact_models import XPathSelector
from mcp_server_selenium.tools.compact import (
    browser_logs,
    get_element_style,
    interact_element,
    local_storage,
    navigate,
    query_elements,
    run_javascript,
    tabs,
    take_screenshot,
    wait_for,
)


class FakeElement:
    tag_name = "input"
    text = "Target"

    def __init__(self, identity="target"):
        self.identity = identity
        self.value = ""
        self.calls = []
        self.click_failures = 0

    def get_attribute(self, name):
        return {
            "id": "target",
            "class": "primary",
            "innerHTML": "Target",
            "outerHTML": "<button id='target'>Target</button>",
            "value": self.value,
        }.get(name, "")

    def is_displayed(self):
        return True

    def is_enabled(self):
        return True

    def is_selected(self):
        return False

    def click(self):
        if self.click_failures:
            self.click_failures -= 1
            raise ElementClickInterceptedException("overlay")
        self.calls.append(("click", None))

    def clear(self):
        self.value = ""
        self.calls.append(("clear", None))

    def send_keys(self, value):
        self.value += str(value)
        self.calls.append(("send_keys", str(value)))

    def screenshot(self, path):
        Path(path).write_bytes(b"element-png")
        return True

    def find_elements(self, by, value):
        return []


class FakeSwitchTo:
    def __init__(self):
        self.frames = []
        self.default_content_calls = 0

    def frame(self, frame):
        self.frames.append(frame)

    def default_content(self):
        self.default_content_calls += 1


class FakeRuntimeSwitch:
    def __init__(self, driver):
        self.driver = driver

    def window(self, handle):
        self.driver.active_handle = handle

    def default_content(self):
        pass

    def frame(self, frame):
        pass


class FakeRuntimeDriver:
    session_id = "runtime-session"
    capabilities = {
        "browserName": "chrome",
        "browserVersion": "140.0",
        "platformName": "linux",
        "chrome": {"chromedriverVersion": "140.1 extra"},
    }

    def __init__(self):
        self.active_handle = "tab-2"
        self.window_handles = ["tab-1", "tab-2"]
        self.urls = {
            "tab-1": "https://one.test/",
            "tab-2": "https://two.test/",
        }
        self.titles = {"tab-1": "First", "tab-2": "Second"}
        self.ready_state = "complete"
        self.navigation_ready_state = "complete"
        self.body_text = "Loaded target"
        self.document_origin = "100"
        self.elements = [FakeElement()]
        self.commands = []
        self.log_reads = []
        self.log_batches = {"browser": [], "performance": []}
        self.async_scripts = []
        self.switch_to = FakeRuntimeSwitch(self)

    @property
    def current_window_handle(self):
        return self.active_handle

    @property
    def current_url(self):
        return self.urls[self.active_handle]

    @property
    def title(self):
        return self.titles[self.active_handle]

    def execute_cdp_cmd(self, command, params):
        self.commands.append((command, params))
        if command == "Page.navigate":
            self.urls[self.active_handle] = params["url"].replace(
                "/redirect", "/final"
            )
            self.ready_state = self.navigation_ready_state
            return {"frameId": "frame", "loaderId": "loader"}
        if command == "Page.getLayoutMetrics":
            return {"cssContentSize": {"width": 1200, "height": 3000}}
        if command == "Page.captureScreenshot":
            return {"data": base64.b64encode(b"full-page-png").decode()}
        return {}

    def execute_script(self, script, *args):
        if "timeOrigin" in script:
            return self.document_origin
        if "readyState" in script:
            return self.ready_state
        if "innerText" in script:
            return self.body_text
        if "document.styleSheets" in script:
            return {"inline": "color:red", "applied_rules": [], "truncated": False}
        if "getComputedStyle" in script:
            return {"properties": {"color": "red"}, "truncated": False}
        if "descriptor" in script:
            self.elements[0].value = args[1]
            return self.elements[0].value
        if "dispatchEvent" in script:
            return self.elements[0].value
        if "scrollIntoView" in script:
            return None
        return "//*[@id=\"target\"]"

    def find_elements(self, by, value):
        return list(self.elements)

    def get_log(self, log_type):
        self.log_reads.append(log_type)
        batches = self.log_batches.setdefault(log_type, [])
        return batches.pop(0) if batches else []

    def save_screenshot(self, path):
        Path(path).write_bytes(b"viewport-png")
        return True

    def set_script_timeout(self, timeout):
        self.script_timeout = timeout

    def execute_async_script(self, script):
        self.async_scripts.append(script)
        if "throw new Error" in script:
            return {
                "ok": False,
                "error": {"code": "javascript_exception", "message": "boom"},
            }
        return {
            "ok": True,
            "result": {
                "type": "object",
                "value": {
                    "missing": {"type": "undefined"},
                    "nothing": {"type": "null", "value": None},
                    "node": {"type": "element", "value": {"tag_name": "input"}},
                    "cycle": {"type": "circular"},
                    "promise": {"type": "number", "value": 42},
                },
            },
        }


class FakeElementDriver:
    def __init__(self):
        self.session_id = "element-session"
        self.current_window_handle = "tab-1"
        self.current_url = "https://example.test/"
        self.document_origin = "100"
        self.switch_to = FakeSwitchTo()
        self.elements = []

    def find_element(self, by, value):
        return "iframe"

    def find_elements(self, by, value):
        return list(self.elements)

    def execute_script(self, script, *args):
        if "timeOrigin" in script:
            return self.document_origin
        return "//*[@id=\"target\"]"


class FakeLogDriver:
    def __init__(self, **batches):
        self.session_id = "log-session"
        self.batches = {key: list(value) for key, value in batches.items()}
        self.log_reads = []

    def get_log(self, log_type):
        self.log_reads.append(log_type)
        batches = self.batches.setdefault(log_type, [])
        batch = batches.pop(0) if batches else []
        if isinstance(batch, Exception):
            raise batch
        return batch


class FakeSelect:
    def __init__(self, element):
        self.element = element
        self.all_selected_options = [type("Option", (), {"text": "Chosen"})()]

    def select_by_value(self, value):
        self.element.calls.append(("select", value))

    def select_by_visible_text(self, value):
        self.element.calls.append(("select_text", value))

    def select_by_index(self, value):
        self.element.calls.append(("select_index", value))


class FakeActions:
    def __init__(self, driver):
        self.driver = driver

    def move_to_element(self, element):
        element.calls.append(("hover", None))
        return self

    def perform(self):
        return None


class ExpiredResponseDriver:
    def execute_cdp_cmd(self, command, params):
        raise RuntimeError(
            "No resource with given identifier found\n"
            "  (Session info: chrome=140)\nStacktrace:\n" + "frame\n" * 1000
        )


class CompactToolParityTests(unittest.TestCase):
    def setUp(self):
        locator_registry.clear()
        diagnostics_broker.clear()

    def test_mutating_tab_actions_delegate_without_contract_changes(self):
        with (
            patch("mcp_server_selenium.tools.compact.open_tab", return_value="opened") as open_tab,
            patch("mcp_server_selenium.tools.compact.switch_tab", return_value="switched") as switch_tab,
            patch("mcp_server_selenium.tools.compact.close_tab", return_value="closed") as close_tab,
        ):
            self.assertEqual("opened", tabs("open", url="https://example.test"))
            self.assertEqual("switched", tabs("switch", handle="tab-2"))
            self.assertEqual("closed", tabs("close", handle="tab-2"))

        open_tab.assert_called_once_with("https://example.test")
        switch_tab.assert_called_once_with("tab-2")
        close_tab.assert_called_once_with("tab-2")

    def test_local_storage_actions_delegate_all_value_modes(self):
        with (
            patch("mcp_server_selenium.tools.compact.local_storage_add", return_value="added") as add,
            patch("mcp_server_selenium.tools.compact.local_storage_read", return_value="read") as read,
            patch("mcp_server_selenium.tools.compact.local_storage_remove", return_value="removed") as remove,
            patch("mcp_server_selenium.tools.compact.local_storage_read_all", return_value="all") as read_all,
            patch("mcp_server_selenium.tools.compact.local_storage_remove_all", return_value="cleared") as remove_all,
        ):
            self.assertEqual(
                "added",
                local_storage(
                    "add",
                    key="settings",
                    object_value={},
                    create_empty_object=True,
                ),
            )
            self.assertEqual("read", local_storage("read", key="settings"))
            self.assertEqual("removed", local_storage("remove", key="settings"))
            self.assertEqual("all", local_storage("read_all"))
            self.assertEqual("cleared", local_storage("remove_all"))

        add.assert_called_once_with("settings", "", {}, False, True)
        read.assert_called_once_with("settings")
        remove.assert_called_once_with("settings")
        read_all.assert_called_once_with()
        remove_all.assert_called_once_with()

    def test_locator_references_re_resolve_bound_and_invalidate_by_document(self):
        driver = FakeElementDriver()
        driver.elements = [FakeElement("first")]
        selector = {
            "type": "fields",
            "value": {"id": "target", "attribute:data-test": "value"},
            "frame": "frame",
        }
        with patch(
            "mcp_server_selenium.tools.compact.ensure_driver_initialized",
            return_value=driver,
        ):
            first = json.loads(query_elements("one", selector, return_html=True))
            element_ref = first["elements"][0]["element_ref"]
            driver.elements = [FakeElement("replacement")]
            resolved = json.loads(
                query_elements("one", {"type": "ref", "value": element_ref})
            )
            driver.document_origin = "200"
            stale = json.loads(
                query_elements("one", {"type": "ref", "value": element_ref})
            )

        self.assertTrue(first["ok"])
        self.assertTrue(resolved["ok"])
        self.assertNotEqual(
            element_ref, resolved["elements"][0]["element_ref"]
        )
        self.assertEqual("stale_element_ref", stale["error"]["code"])
        self.assertEqual(["iframe", "iframe"], driver.switch_to.frames)
        self.assertTrue(
            all(isinstance(record.selector, dict) for record in locator_registry._records.values())
        )

        registry = LocatorRegistry(max_entries=2)
        driver.document_origin = "300"
        scope = registry.current_scope(driver)
        for index in range(3):
            registry.add(
                XPathSelector(type="xpath", value=f"//button[{index + 1}]"),
                scope,
            )
        self.assertEqual(2, len(registry._records))

    def test_wait_navigation_tab_metadata_and_isolated_downloads(self):
        driver = FakeRuntimeDriver()
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(server, "workspace_root", Path(temp_dir)),
                patch.object(
                    server, "download_directory", Path("artifacts/downloads")
                ),
                patch.object(server, "_configured_download_session", ""),
                patch(
                    "mcp_server_selenium.tools.compact.ensure_driver_initialized",
                    return_value=driver,
                ),
            ):
                ready = json.loads(wait_for("ready", state="complete", timeout=0))
                element = json.loads(
                    wait_for(
                        "element",
                        state="enabled",
                        selector={"type": "css", "value": "#target"},
                        timeout=0,
                    )
                )
                text = json.loads(wait_for("text", value="Loaded", timeout=0))
                network = json.loads(
                    wait_for("network_idle", timeout=0, quiet_ms=0)
                )
                redirected = json.loads(
                    navigate(
                        "http://local.test/redirect",
                        wait_until="complete",
                        timeout=0,
                    )
                )
                initiated = json.loads(
                    navigate(
                        "local.test/pending",
                        wait_until="initiated",
                        timeout=0,
                    )
                )
                driver.navigation_ready_state = "loading"
                timed_out = json.loads(
                    navigate("local.test/slow", wait_until="complete", timeout=0)
                )
                metadata = json.loads(tabs("list"))
                download_path = server.configure_download_directory(driver)
                server.configure_download_directory(driver)

                self.assertTrue(
                    all(item["ok"] for item in (ready, element, text, network))
                )
                self.assertEqual("http://local.test/final", redirected["final_url"])
                self.assertTrue(initiated["navigation_pending"])
                self.assertTrue(timed_out["timed_out"])
                self.assertEqual("loading", timed_out["ready_state"])
                self.assertEqual("tab-2", metadata["active_handle"])
                self.assertEqual("tab-2", driver.current_window_handle)
                self.assertEqual(
                    ["loading", "loading"],
                    [tab["ready_state"] for tab in metadata["tabs"]],
                )
                self.assertEqual("140.0", metadata["browser"]["version"])
                self.assertEqual("140.1", metadata["browser"]["driver_version"])
                self.assertEqual(str(download_path), metadata["download_directory"])
                self.assertTrue(download_path.is_dir())
                download_commands = [
                    command
                    for command, _ in driver.commands
                    if command.endswith("setDownloadBehavior")
                ]
                self.assertEqual(["Browser.setDownloadBehavior"], download_commands)

    def test_interactions_report_retries_postconditions_and_all_actions(self):
        driver = FakeRuntimeDriver()
        with patch(
            "mcp_server_selenium.tools.compact.ensure_driver_initialized",
            return_value=driver,
        ):
            element_ref = json.loads(
                query_elements("one", {"type": "css", "value": "#target"})
            )["elements"][0]["element_ref"]
            driver.elements[0].click_failures = 1
            with tempfile.NamedTemporaryFile() as upload:
                with (
                    patch(
                        "mcp_server_selenium.tools.compact_interactions.Select",
                        FakeSelect,
                    ),
                    patch(
                        "mcp_server_selenium.tools.compact_interactions.ActionChains",
                        FakeActions,
                    ),
                ):
                    results = {
                        "click": json.loads(
                            interact_element("click", element_ref, timeout=1)
                        ),
                        "clear": json.loads(interact_element("clear", element_ref)),
                        "type": json.loads(
                            interact_element("type", element_ref, input_value="typed")
                        ),
                        "set_value": json.loads(
                            interact_element(
                                "set_value", element_ref, input_value="set"
                            )
                        ),
                        "press_key": json.loads(
                            interact_element("press_key", element_ref, key="ENTER")
                        ),
                        "select_option": json.loads(
                            interact_element(
                                "select_option",
                                element_ref,
                                option_by="value",
                                option_value="chosen",
                            )
                        ),
                        "hover": json.loads(interact_element("hover", element_ref)),
                        "scroll_into_view": json.loads(
                            interact_element("scroll_into_view", element_ref)
                        ),
                        "upload_file": json.loads(
                            interact_element(
                                "upload_file", element_ref, file_path=upload.name
                            )
                        ),
                    }

        self.assertTrue(all(result["ok"] for result in results.values()))
        self.assertEqual(2, results["click"]["attempts"])
        self.assertEqual("set", results["set_value"]["element"]["value"])
        self.assertEqual(
            ["input", "change"],
            results["set_value"]["event_dispatch"]["events"],
        )
        self.assertTrue(
            all(
                {"attempts", "url", "element", "event_dispatch"} <= result.keys()
                for result in results.values()
            )
        )

    def test_artifact_style_javascript_and_response_contracts(self):
        driver = FakeRuntimeDriver()
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(server, "workspace_root", Path(temp_dir)),
                patch(
                    "mcp_server_selenium.tools.compact.ensure_driver_initialized",
                    return_value=driver,
                ),
            ):
                element_ref = json.loads(
                    query_elements("one", {"type": "css", "value": "#target"})
                )["elements"][0]["element_ref"]
                screenshots = [
                    json.loads(
                        take_screenshot(
                            "evidence",
                            "shots",
                            mode,
                            element_ref if mode == "element" else "",
                        )
                    )
                    for mode in ("viewport", "full_page", "element")
                ]
                styles = json.loads(get_element_style(element_ref))
                html = json.loads(
                    get_element_style(element_ref, return_html=True)
                )
                plain = json.loads(
                    run_javascript("return Promise.resolve(document.body)")
                )
                self.assertEqual([], driver.log_reads)
                driver.log_batches["browser"] = [
                    [{"level": "INFO", "source": "console-api", "message": "old", "timestamp": 1}],
                    [{"level": "WARNING", "source": "console-api", "message": "fresh", "timestamp": 2}],
                ]
                captured = json.loads(
                    run_javascript(
                        "console.warn('fresh'); return undefined",
                        capture_console=True,
                    )
                )

        self.assertTrue(all(result["ok"] for result in screenshots))
        self.assertEqual(
            ["evidence.png", "evidence-2.png", "evidence-3.png"],
            [Path(result["path"]).name for result in screenshots],
        )
        self.assertTrue(styles["ok"] and "computed_style" in styles)
        self.assertTrue(html["ok"] and "html" in html)
        self.assertNotIn("all_styles", html)
        self.assertEqual("object", plain["result"]["type"])
        self.assertEqual(
            ["fresh"],
            [entry["message"] for entry in captured["console"]["events"]],
        )
        old = diagnostics_broker.read("console", "peek", 0, 10, 0, True)
        self.assertEqual(["old"], [entry["message"] for entry in old["events"]])
        self.assertIn("MAX_DEPTH = 5", driver.async_scripts[0])
        expired = response_body(ExpiredResponseDriver(), "request-1")
        self.assertEqual("response_body_expired", expired["error"]["code"])
        self.assertTrue(expired["error"]["hint"])
        self.assertLessEqual(len(expired["error"]["message"]), 500)
        self.assertNotIn("Stacktrace", expired["error"]["message"])

    def test_diagnostics_broker_bounds_cursor_consumption_and_redaction(self):
        request = {
            "method": "Network.requestWillBeSent",
            "params": {
                "requestId": "request-1",
                "type": "Fetch",
                "statusCode": 200,
                "request": {
                    "url": "https://api.test/data?token=secret&safe=yes",
                    "headers": {"Authorization": "Bearer secret", "Accept": "json"},
                    "postData": "password=secret",
                },
            },
        }
        finished = {
            "method": "Network.loadingFinished",
            "params": {"requestId": "request-1"},
        }
        performance = [
            {
                "timestamp": timestamp,
                "message": json.dumps({"message": event}),
            }
            for timestamp, event in ((40, request), (50, finished))
        ]
        driver = FakeLogDriver(
            browser=[[
                {"level": "INFO", "message": "first", "timestamp": 10},
                {"level": "WARNING", "message": "second", "timestamp": 20},
                {"level": "SEVERE", "message": "third", "timestamp": 30},
            ]],
            performance=[performance],
        )
        broker = DiagnosticsBroker(console_limit=2, network_limit=4)
        broker.drain_console(driver, wait_seconds=0)
        peek = broker.read("console", "peek", 0, 1, 0, True)
        consume = broker.read("console", "consume", 0, 1, 0, True)
        remainder = broker.read(
            "console", "peek", consume["next_cursor"], 10, 0, True
        )
        state = broker.network_state(driver)
        redacted = broker.read("network", "peek", 0, 10, 0, True)
        raw = broker.read("network", "peek", 0, 10, 0, False)
        requests = broker.read(
            "network", "peek", 0, 10, 0, True, event_type="request"
        )
        finished_events = broker.read(
            "network", "peek", 0, 10, 0, True, event_type="finished"
        )

        self.assertEqual(1, peek["dropped_events"])
        self.assertTrue(peek["has_more"])
        self.assertEqual(peek["events"], consume["events"])
        self.assertEqual("third", remainder["events"][0]["message"])
        self.assertEqual([], state["inflight"])
        self.assertEqual(2, len(redacted["events"]))
        self.assertEqual(
            ["Network.requestWillBeSent"],
            [event["method"] for event in requests["events"]],
        )
        self.assertEqual(
            ["Network.loadingFinished"],
            [event["method"] for event in finished_events["events"]],
        )
        safe_request = redacted["events"][0]["params"]["request"]
        self.assertNotIn("secret", safe_request["url"])
        self.assertEqual("[REDACTED]", safe_request["headers"]["Authorization"])
        self.assertEqual("[REDACTED]", safe_request["postData"])
        self.assertEqual(200, redacted["events"][0]["params"]["statusCode"])
        self.assertEqual(
            "Bearer secret",
            raw["events"][0]["params"]["request"]["headers"]["Authorization"],
        )

        driver.session_id = "another-session"
        broker.drain_console(driver, wait_seconds=0)
        self.assertEqual([], broker.read("console", "peek", 0, 10, 0, True)["events"])

if __name__ == "__main__":
    unittest.main()
