import asyncio
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import struct
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp_server_selenium.drivers.normal_chrome import NormalChromeDriver


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_TOOLS = {
    "navigate", "list_tabs", "open_tab", "switch_tab", "close_tab",
    "take_screenshot", "check_page_ready", "get_console_logs",
    "get_network_logs", "get_response", "local_storage_add",
    "local_storage_read", "local_storage_remove", "local_storage_read_all",
    "local_storage_remove_all", "get_an_element", "get_direct_children",
    "get_elements", "click_to_element", "set_value_to_input_element",
    "run_javascript_in_console", "run_javascript_and_get_console_output",
    "get_style_an_element",
}
COMPACT_TOOLS = {
    "navigate", "tabs", "take_screenshot", "wait_for",
    "browser_logs", "local_storage", "query_elements", "interact_element",
    "run_javascript", "get_element_style",
}
FIXTURE_HTML = """<!doctype html>
<title>Selenium compact E2E</title>
<style>body{min-height:2600px} #hidden-target{display:none} #scroll-target{margin-top:1800px}</style>
<h1 id="title">Compact fixture</h1>
<input id="name" value="initial">
<button id="replaceable" onclick="document.getElementById('status').textContent='clicked'">Click</button>
<select id="choice" onchange="document.getElementById('status').textContent='selected-'+this.value">
  <option value="one">One</option><option value="two">Two</option>
</select>
<div id="hover-target" onmouseenter="document.getElementById('status').textContent='hovered'">Hover</div>
<input id="upload" type="file">
<a id="download-link" href="/download" download="e2e-download.txt">Download</a>
<div id="status">idle</div>
<div id="hidden-target">hidden</div>
<div id="parent"><span class="child">one</span><span class="child">two</span></div>
<iframe id="fixture-frame" src="/frame.html"></iframe>
<div id="scroll-target">bottom target</div>
<script>
const nameInput = document.getElementById('name');
nameInput.dataset.inputEvents = '0';
nameInput.dataset.changeEvents = '0';
nameInput.addEventListener('input', () => nameInput.dataset.inputEvents = String(Number(nameInput.dataset.inputEvents) + 1));
nameInput.addEventListener('change', () => nameInput.dataset.changeEvents = String(Number(nameInput.dataset.changeEvents) + 1));
nameInput.addEventListener('keydown', event => { if (event.key === 'Enter') document.getElementById('status').textContent = 'enter'; });
</script>
"""
FRAME_HTML = """<!doctype html><title>Frame</title><button id="frame-button" onclick="this.textContent='frame-clicked'">Frame button</button>"""


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        path = self.path.partition("?")[0]
        if path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/index.html?redirected=1")
            self.end_headers()
            return
        if path == "/api/data":
            body = json.dumps({"ok": True, "source": "e2e-api"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/download":
            body = b"selenium compact download\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header(
                "Content-Disposition", 'attachment; filename="e2e-download.txt"'
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


class McpStdioE2ETest(unittest.TestCase):
    @staticmethod
    def _result_text(result) -> str:
        texts = [item.text for item in result.content if hasattr(item, "text")]
        if result.isError:
            raise AssertionError("MCP tool call failed: " + "\n".join(texts))
        return "\n".join(texts)

    @classmethod
    def _typed_value(cls, result):
        value_type = result.get("type")
        if value_type in {"undefined", "circular", "max_depth"}:
            return value_type
        if value_type == "array":
            return [cls._typed_value(item) for item in result.get("value", [])]
        if value_type == "object":
            return {
                key: cls._typed_value(value)
                for key, value in result.get("value", {}).items()
            }
        return result.get("value")

    async def _call(self, session, tool_name: str, arguments=None) -> str:
        return self._result_text(
            await session.call_tool(tool_name, arguments or {})
        )

    async def _run_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            profile_path = temp_path / "chrome-profile"
            workspace_path = temp_path / "workspace"
            workspace_path.mkdir()
            screenshot_path = (
                workspace_path / "tmp/selenium-screenshot/e2e-active-tab.png"
            )
            absolute_screenshot_directory = temp_path / "absolute-screenshots"
            absolute_screenshot_path = (
                absolute_screenshot_directory / "e2e-absolute-directory.png"
            )
            environment = dict(os.environ, PYTHONPATH=str(PROJECT_ROOT / "src"))
            server = StdioServerParameters(
                command=sys.executable,
                args=[
                    "-m",
                    "mcp_server_selenium",
                    "--tool-profile",
                    "legacy",
                    "--user_data_dir",
                    str(profile_path),
                    "--workspace_root",
                    str(workspace_path),
                ],
                env=environment,
                cwd=PROJECT_ROOT,
            )

            try:
                async with stdio_client(server) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        initialization = await session.initialize()
                        tools = (await session.list_tools()).tools
                        discovered_tools = {tool.name: tool for tool in tools}
                        self.assertEqual(LEGACY_TOOLS, set(discovered_tools))
                        records = [
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "inputSchema": tool.inputSchema,
                            }
                            for tool in tools
                        ]
                        self.assertLess(
                            len(
                                json.dumps(
                                    records,
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                ).encode()
                            ),
                            12 * 1024,
                        )
                        screenshot_schema = discovered_tools["take_screenshot"].inputSchema
                        screenshot_description = (
                            discovered_tools["take_screenshot"].description or ""
                        )
                        normalized_screenshot_description = " ".join(
                            screenshot_description.split()
                        )
                        self.assertIn("file_name", screenshot_schema["required"])
                        self.assertNotIn("save_path", screenshot_schema["properties"])
                        self.assertIn(
                            "Prefer an absolute directory inside your current workspace",
                            normalized_screenshot_description,
                        )
                        self.assertEqual(
                            "tmp/selenium-screenshot",
                            screenshot_schema["properties"]["directory"]["default"],
                        )
                        self.assertIn(
                            "exactly one active tab context", initialization.instructions or ""
                        )
                        self.assertIn(
                            "must be serialized", initialization.instructions or ""
                        )
                        for tool_name in ("list_tabs", "open_tab", "switch_tab", "close_tab"):
                            self.assertIn(
                                "serialize",
                                (discovered_tools[tool_name].description or "").lower(),
                            )

                        before = json.loads(self._result_text(await session.call_tool("list_tabs")))
                        opened = json.loads(
                            self._result_text(
                                await session.call_tool(
                                    "open_tab",
                                    {"url": "data:text/html,<title>E2E Tab</title><h1>e2e</h1>"},
                                )
                            )
                        )
                        after_open = json.loads(
                            self._result_text(await session.call_tool("list_tabs"))
                        )
                        after_handles = {tab["handle"] for tab in after_open["tabs"]}

                        self.assertIn(before["active_handle"], after_handles)
                        self.assertIn(opened["handle"], after_handles)
                        switched = json.loads(
                            self._result_text(
                                await session.call_tool(
                                    "switch_tab", {"handle": before["active_handle"]}
                                )
                            )
                        )
                        closed = json.loads(
                            self._result_text(
                                await session.call_tool(
                                    "close_tab", {"handle": opened["handle"]}
                                )
                            )
                        )
                        screenshot_result = self._result_text(
                            await session.call_tool(
                                "take_screenshot", {"file_name": "e2e-active-tab"}
                            )
                        )
                        absolute_screenshot_result = self._result_text(
                            await session.call_tool(
                                "take_screenshot",
                                {
                                    "file_name": "e2e-absolute-directory",
                                    "directory": str(absolute_screenshot_directory),
                                },
                            )
                        )

                        self.assertEqual(before["active_handle"], switched["handle"])
                        self.assertNotIn(opened["handle"], closed["remaining_handles"])
                        self.assertIn(str(screenshot_path), screenshot_result)
                        self.assertTrue(screenshot_path.is_file())
                        self.assertFalse(screenshot_path.is_dir())
                        self.assertIn(
                            str(absolute_screenshot_path), absolute_screenshot_result
                        )
                        self.assertTrue(absolute_screenshot_path.is_file())
            finally:
                NormalChromeDriver(user_data_dir=str(profile_path))._kill_chrome_with_user_data_dir()

    async def _run_compact_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            profile_path = temp_path / "chrome-profile"
            workspace_path = temp_path / "workspace"
            workspace_path.mkdir()
            (workspace_path / "index.html").write_text(
                FIXTURE_HTML,
                encoding="utf-8",
            )
            (workspace_path / "frame.html").write_text(
                FRAME_HTML,
                encoding="utf-8",
            )
            upload_path = workspace_path / "upload-evidence.txt"
            upload_path.write_text("upload evidence", encoding="utf-8")
            download_path = workspace_path / "downloads"
            screenshot_directory = workspace_path / "evidence"

            handler = functools.partial(
                QuietHandler,
                directory=str(workspace_path),
            )
            http_server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            http_thread = threading.Thread(
                target=http_server.serve_forever,
                daemon=True,
            )
            http_thread.start()
            fixture_url = (
                f"http://127.0.0.1:{http_server.server_address[1]}/index.html"
            )
            redirect_url = (
                f"http://127.0.0.1:{http_server.server_address[1]}/redirect"
            )

            environment = dict(os.environ, PYTHONPATH=str(PROJECT_ROOT / "src"))
            server = StdioServerParameters(
                command=sys.executable,
                args=[
                    "-m",
                    "mcp_server_selenium",
                    "--user_data_dir",
                    str(profile_path),
                    "--workspace_root",
                    str(workspace_path),
                    "--download_dir",
                    str(download_path),
                ],
                env=environment,
                cwd=PROJECT_ROOT,
            )

            try:
                async with stdio_client(server) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        initialization = await session.initialize()
                        tools = (await session.list_tools()).tools
                        discovered = {tool.name: tool for tool in tools}
                        self.assertEqual(COMPACT_TOOLS, set(discovered))
                        records = [
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "inputSchema": tool.inputSchema,
                            }
                            for tool in tools
                        ]
                        self.assertLess(
                            len(
                                json.dumps(
                                    records,
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                ).encode()
                            ),
                            12 * 1024,
                        )
                        self.assertIn(
                            "Recommended workflow",
                            initialization.instructions or "",
                        )
                        self.assertIn(
                            "shared mutable state",
                            initialization.instructions or "",
                        )
                        self.assertFalse(
                            discovered["run_javascript"].inputSchema[
                                "properties"
                            ]["capture_console"]["default"]
                        )
                        event_type_schema = discovered["browser_logs"].inputSchema[
                            "properties"
                        ]["event_type"]
                        self.assertEqual("all", event_type_schema["default"])
                        self.assertEqual(
                            {"all", "request", "response", "finished", "failed"},
                            set(event_type_schema["enum"]),
                        )
                        self.assertIn(
                            "discriminator",
                            json.dumps(discovered["query_elements"].inputSchema),
                        )
                        self.assertIn(
                            "discriminator",
                            json.dumps(discovered["wait_for"].inputSchema),
                        )
                        expected_live_examples = {
                            "browser_logs": {
                                "action": "network",
                                "event_type": "response",
                            },
                            "wait_for": {
                                "condition": "element",
                                "state": "visible",
                                "selector": {"type": "css", "value": "#x"},
                            },
                            "interact_element": {
                                "action": "type",
                                "element_ref": "el_REF",
                                "input_value": "x",
                            },
                        }
                        for tool_name, expected in expected_live_examples.items():
                            encoded = discovered[tool_name].description.split(
                                "Example JSON: ", 1
                            )[1]
                            self.assertEqual(expected, json.loads(encoded))

                        async def call_json(tool_name, arguments=None):
                            return json.loads(
                                await self._call(session, tool_name, arguments)
                            )

                        async def query_ref(selector):
                            result = await call_json(
                                "query_elements",
                                {"action": "one", "selector": selector},
                            )
                            self.assertTrue(result["ok"], result)
                            return result["elements"][0]["element_ref"]

                        initiated = await call_json(
                            "navigate",
                            {
                                "url": fixture_url,
                                "wait_until": "initiated",
                                "timeout": 10,
                            },
                        )
                        self.assertTrue(initiated["ok"])
                        self.assertTrue(initiated["navigation_pending"])
                        self.assertTrue(
                            (
                                await call_json(
                                    "wait_for",
                                    {
                                        "condition": "ready",
                                        "state": "complete",
                                        "timeout": 10,
                                    },
                                )
                            )["ok"]
                        )
                        interactive = await call_json(
                            "navigate",
                            {
                                "url": fixture_url,
                                "wait_until": "interactive",
                                "timeout": 10,
                            },
                        )
                        self.assertTrue(interactive["ok"])
                        redirected = await call_json(
                            "navigate",
                            {
                                "url": redirect_url,
                                "wait_until": "complete",
                                "timeout": 10,
                            },
                        )
                        self.assertTrue(redirected["ok"])
                        self.assertIn("/index.html?redirected=1", redirected["final_url"])
                        network_navigation = await call_json(
                            "navigate",
                            {
                                "url": fixture_url,
                                "wait_until": "network_idle",
                                "timeout": 10,
                                "quiet_ms": 100,
                            },
                        )
                        self.assertTrue(network_navigation["ok"])

                        body_result = await call_json(
                            "run_javascript",
                            {"javascript_code": "return document.body.innerText"},
                        )
                        body_text = self._typed_value(body_result["result"])
                        self.assertTrue(
                            (
                                await call_json(
                                    "wait_for",
                                    {
                                        "condition": "text",
                                        "state": "present",
                                        "value": body_text,
                                        "match": "equals",
                                        "timeout": 1,
                                    },
                                )
                            )["ok"]
                        )
                        scoped_text = await call_json(
                            "wait_for",
                            {
                                "condition": "text",
                                "state": "present",
                                "value": "one\ntwo",
                                "selector": {"type": "css", "value": ".child"},
                                "match": "equals",
                                "timeout": 1,
                            },
                        )
                        self.assertTrue(scoped_text["ok"], scoped_text)

                        for arguments in (
                            {"condition": "url", "value": "/index.html", "timeout": 1},
                            {
                                "condition": "element",
                                "state": "present",
                                "selector": {"type": "css", "value": "#title"},
                                "timeout": 1,
                            },
                            {
                                "condition": "element",
                                "state": "visible",
                                "selector": {"type": "xpath", "value": "//*[@id='title']"},
                                "timeout": 1,
                            },
                            {
                                "condition": "element",
                                "state": "enabled",
                                "selector": {"type": "css", "value": "#replaceable"},
                                "timeout": 1,
                            },
                            {
                                "condition": "element",
                                "state": "hidden",
                                "selector": {"type": "css", "value": "#hidden-target"},
                                "timeout": 1,
                            },
                            {
                                "condition": "text",
                                "state": "present",
                                "value": "Compact fixture",
                                "selector": {"type": "css", "value": "#title"},
                                "timeout": 1,
                            },
                            {"condition": "network_idle", "quiet_ms": 50, "timeout": 2},
                        ):
                            self.assertTrue(
                                (await call_json("wait_for", arguments))["ok"],
                                arguments,
                            )
                        await call_json(
                            "run_javascript",
                            {
                                "javascript_code": "setTimeout(() => { const node=document.createElement('div'); node.id='dynamic-target'; node.textContent='dynamic ready'; document.body.appendChild(node); }, 150); return true"
                            },
                        )
                        self.assertTrue(
                            (
                                await call_json(
                                    "wait_for",
                                    {
                                        "condition": "element",
                                        "state": "visible",
                                        "selector": {"type": "css", "value": "#dynamic-target"},
                                        "timeout": 2,
                                    },
                                )
                            )["ok"]
                        )
                        timed_out = await call_json(
                            "wait_for",
                            {
                                "condition": "url",
                                "value": "/never-arrives",
                                "timeout": 0.1,
                                "poll_interval": 0.05,
                            },
                        )
                        self.assertTrue(timed_out["timed_out"])
                        self.assertIn("observation", timed_out)

                        title_query = await call_json(
                            "query_elements",
                            {
                                "action": "one",
                                "selector": {"type": "xpath", "value": "//*[@id='title']"},
                                "return_html": True,
                            },
                        )
                        title_ref = title_query["elements"][0]["element_ref"]
                        many = await call_json(
                            "query_elements",
                            {
                                "action": "many",
                                "selector": {"type": "css", "value": ".child"},
                                "page_size": 1,
                            },
                        )
                        children = await call_json(
                            "query_elements",
                            {
                                "action": "children",
                                "selector": {
                                    "type": "fields",
                                    "value": {"id": "parent", "element_type": "div"},
                                },
                            },
                        )
                        ref_query = await call_json(
                            "query_elements",
                            {
                                "action": "one",
                                "selector": {"type": "ref", "value": title_ref},
                            },
                        )
                        frame_ref = await query_ref(
                            {
                                "type": "css",
                                "value": "#frame-button",
                                "frame": "fixture-frame",
                            }
                        )
                        self.assertEqual(2, many["matched"])
                        self.assertEqual(1, many["returned"])
                        self.assertTrue(many["has_more"])
                        self.assertEqual(2, children["matched"])
                        self.assertTrue(ref_query["ok"])

                        input_ref = await query_ref({"type": "css", "value": "#name"})
                        button_ref = await query_ref(
                            {"type": "css", "value": "#replaceable"}
                        )
                        select_ref = await query_ref(
                            {"type": "css", "value": "#choice"}
                        )
                        hover_ref = await query_ref(
                            {"type": "css", "value": "#hover-target"}
                        )
                        scroll_ref = await query_ref(
                            {"type": "css", "value": "#scroll-target"}
                        )
                        upload_ref = await query_ref(
                            {"type": "css", "value": "#upload"}
                        )
                        await call_json(
                            "run_javascript",
                            {
                                "javascript_code": "const old=document.getElementById('replaceable'); old.replaceWith(old.cloneNode(true)); return true"
                            },
                        )
                        interactions = [
                            await call_json("interact_element", {"action": "clear", "element_ref": input_ref}),
                            await call_json(
                                "interact_element",
                                {"action": "type", "element_ref": input_ref, "input_value": "typed"},
                            ),
                            await call_json(
                                "interact_element",
                                {"action": "press_key", "element_ref": input_ref, "key": "ENTER"},
                            ),
                            await call_json(
                                "interact_element",
                                {"action": "set_value", "element_ref": input_ref, "input_value": "updated"},
                            ),
                            await call_json("interact_element", {"action": "click", "element_ref": button_ref}),
                            await call_json(
                                "interact_element",
                                {
                                    "action": "select_option",
                                    "element_ref": select_ref,
                                    "option_by": "value",
                                    "option_value": "two",
                                },
                            ),
                            await call_json("interact_element", {"action": "hover", "element_ref": hover_ref}),
                            await call_json(
                                "interact_element",
                                {"action": "scroll_into_view", "element_ref": scroll_ref},
                            ),
                            await call_json(
                                "interact_element",
                                {
                                    "action": "upload_file",
                                    "element_ref": upload_ref,
                                    "file_path": str(upload_path),
                                },
                            ),
                            await call_json("interact_element", {"action": "click", "element_ref": frame_ref}),
                        ]
                        self.assertTrue(all(result["ok"] for result in interactions))
                        self.assertEqual(
                            ["input", "change"],
                            interactions[3]["event_dispatch"]["events"],
                        )

                        page_state_result = await call_json(
                            "run_javascript",
                            {
                                "javascript_code": "return {value:document.getElementById('name').value, status:document.getElementById('status').textContent, choice:document.getElementById('choice').value, upload:document.getElementById('upload').value, inputEvents:document.getElementById('name').dataset.inputEvents, changeEvents:document.getElementById('name').dataset.changeEvents}"
                            },
                        )
                        page_state = self._typed_value(page_state_result["result"])
                        self.assertEqual("updated", page_state["value"])
                        self.assertEqual("two", page_state["choice"])
                        self.assertIn("upload-evidence.txt", page_state["upload"])
                        self.assertGreaterEqual(int(page_state["inputEvents"]), 1)
                        self.assertGreaterEqual(int(page_state["changeEvents"]), 1)

                        style = await call_json(
                            "get_element_style",
                            {
                                "element_ref": title_ref,
                                "all_styles": False,
                                "computed_style": True,
                            },
                        )
                        html = await call_json(
                            "get_element_style",
                            {"element_ref": title_ref, "return_html": True},
                        )
                        self.assertTrue(style["ok"])
                        self.assertIn("properties", style["computed_style"])
                        self.assertIn("Compact fixture", html["html"]["outerHTML"])
                        self.assertNotIn("all_styles", html)

                        special = await call_json(
                            "run_javascript",
                            {
                                "javascript_code": "const cycle={}; cycle.self=cycle; return await Promise.resolve({missing:undefined,nothing:null,node:document.getElementById('title'),cycle:cycle,answer:42})"
                            },
                        )
                        special_values = special["result"]["value"]
                        self.assertEqual("undefined", special_values["missing"]["type"])
                        self.assertEqual("null", special_values["nothing"]["type"])
                        self.assertEqual("element", special_values["node"]["type"])
                        self.assertEqual(
                            "circular",
                            special_values["cycle"]["value"]["self"]["type"],
                        )
                        self.assertEqual(42, special_values["answer"]["value"])
                        exception = await call_json(
                            "run_javascript",
                            {"javascript_code": "throw new Error('e2e boom')"},
                        )
                        self.assertEqual(
                            "javascript_exception", exception["error"]["code"]
                        )

                        await call_json(
                            "run_javascript",
                            {
                                "javascript_code": "console.warn('plain-e2e-warning'); console.error('plain-e2e-error')"
                            },
                        )
                        console_peek = await call_json(
                            "browser_logs",
                            {"action": "console", "mode": "peek", "limit": 100},
                        )
                        messages = "\n".join(
                            event["message"] for event in console_peek["events"]
                        )
                        self.assertIn("plain-e2e-warning", messages)
                        self.assertIn("plain-e2e-error", messages)
                        console_peek_again = await call_json(
                            "browser_logs",
                            {"action": "console", "mode": "peek", "limit": 100},
                        )
                        self.assertEqual(
                            console_peek["events"], console_peek_again["events"]
                        )
                        since = min(event["timestamp"] for event in console_peek["events"])
                        self.assertTrue(
                            (
                                await call_json(
                                    "browser_logs",
                                    {
                                        "action": "console",
                                        "mode": "peek",
                                        "since_timestamp": since,
                                        "limit": 100,
                                    },
                                )
                            )["events"]
                        )
                        await call_json(
                            "browser_logs",
                            {"action": "console", "mode": "consume", "limit": 100},
                        )
                        self.assertEqual(
                            [],
                            (
                                await call_json(
                                    "browser_logs",
                                    {"action": "console", "mode": "peek"},
                                )
                            )["events"],
                        )
                        await call_json(
                            "run_javascript",
                            {"javascript_code": "console.error('error-alias-e2e')"},
                        )
                        alias = await call_json(
                            "browser_logs",
                            {
                                "action": "console",
                                "mode": "consume",
                                "log_level": "ERROR",
                            },
                        )
                        self.assertTrue(
                            any(
                                "error-alias-e2e" in event["message"]
                                and event["level"] == "SEVERE"
                                for event in alias["events"]
                            )
                        )
                        await call_json(
                            "run_javascript",
                            {"javascript_code": "console.log('older-e2e')"},
                        )
                        captured = await call_json(
                            "run_javascript",
                            {
                                "javascript_code": "console.log('captured-e2e'); return 7",
                                "capture_console": True,
                            },
                        )
                        self.assertEqual(7, captured["result"]["value"])
                        self.assertTrue(
                            any(
                                "captured-e2e" in event["message"]
                                for event in captured["console"]["events"]
                            )
                        )
                        older = await call_json(
                            "browser_logs",
                            {"action": "console", "mode": "peek", "limit": 100},
                        )
                        self.assertTrue(
                            any("older-e2e" in event["message"] for event in older["events"])
                        )
                        self.assertFalse(
                            any("captured-e2e" in event["message"] for event in older["events"])
                        )

                        fetch = await call_json(
                            "run_javascript",
                            {
                                "javascript_code": "return await fetch('/api/data?token=secret',{headers:{Authorization:'Bearer secret'}}).then(response => response.json())"
                            },
                        )
                        self.assertTrue(fetch["ok"])
                        self.assertTrue(
                            (
                                await call_json(
                                    "wait_for",
                                    {
                                        "condition": "network_idle",
                                        "quiet_ms": 50,
                                        "timeout": 2,
                                    },
                                )
                            )["ok"]
                        )
                        network_page = await call_json(
                            "browser_logs",
                            {
                                "action": "network",
                                "mode": "peek",
                                "limit": 1,
                                "filter_url_by_text": "/api/data",
                            },
                        )
                        self.assertTrue(network_page["has_more"])
                        redacted_network = await call_json(
                            "browser_logs",
                            {
                                "action": "network",
                                "mode": "peek",
                                "limit": 100,
                                "filter_url_by_text": "/api/data",
                            },
                        )
                        raw_network = await call_json(
                            "browser_logs",
                            {
                                "action": "network",
                                "mode": "peek",
                                "limit": 100,
                                "filter_url_by_text": "/api/data",
                                "redact": False,
                            },
                        )
                        redacted_text = json.dumps(redacted_network)
                        raw_text = json.dumps(raw_network)
                        self.assertNotIn("Bearer secret", redacted_text)
                        self.assertNotIn("token=secret", redacted_text)
                        self.assertIn("[REDACTED]", redacted_text)
                        self.assertIn("token=secret", raw_text)
                        filtered_responses = await call_json(
                            "browser_logs",
                            {
                                "action": "network",
                                "mode": "peek",
                                "limit": 100,
                                "filter_url_by_text": "/api/data",
                                "event_type": "response",
                            },
                        )
                        self.assertTrue(filtered_responses["events"])
                        self.assertTrue(
                            all(
                                event["method"].startswith("Network.responseReceived")
                                for event in filtered_responses["events"]
                            )
                        )
                        response_event = next(
                            event
                            for event in raw_network["events"]
                            if event.get("method") == "Network.responseReceived"
                        )
                        response = await call_json(
                            "browser_logs",
                            {
                                "action": "response",
                                "request_id": response_event["params"]["requestId"],
                            },
                        )
                        self.assertTrue(response["ok"])
                        self.assertIn("e2e-api", response["body"])
                        unavailable = await call_json(
                            "browser_logs",
                            {"action": "response", "request_id": "missing-e2e-id"},
                        )
                        self.assertFalse(unavailable["ok"])
                        self.assertIn("hint", unavailable["error"])
                        self.assertLessEqual(
                            len(unavailable["error"]["message"]), 500
                        )
                        self.assertNotIn(
                            "Stacktrace", unavailable["error"]["message"]
                        )
                        self.assertNotIn(
                            "Session info", unavailable["error"]["message"]
                        )

                        self.assertIn(
                            "Successfully added",
                            await self._call(
                                session,
                                "local_storage",
                                {"action": "add", "key": "e2e", "string_value": "value"},
                            ),
                        )
                        self.assertIn(
                            "value",
                            await self._call(
                                session,
                                "local_storage",
                                {"action": "read", "key": "e2e"},
                            ),
                        )
                        self.assertEqual(
                            {"e2e": "value"},
                            json.loads(
                                await self._call(
                                    session, "local_storage", {"action": "read_all"}
                                )
                            ),
                        )
                        self.assertIn(
                            "Successfully removed",
                            await self._call(
                                session,
                                "local_storage",
                                {"action": "remove", "key": "e2e"},
                            ),
                        )
                        await self._call(
                            session,
                            "local_storage",
                            {
                                "action": "add",
                                "key": "empty-object",
                                "object_value": {},
                                "create_empty_object": True,
                            },
                        )
                        self.assertIn(
                            "Successfully removed all",
                            await self._call(
                                session, "local_storage", {"action": "remove_all"}
                            ),
                        )

                        tab_state = await call_json(
                            "tabs", {"action": "list"}
                        )
                        self.assertEqual(str(download_path), tab_state["download_directory"])
                        self.assertTrue(tab_state["browser"]["version"])
                        self.assertTrue(
                            all("ready_state" in tab for tab in tab_state["tabs"])
                        )
                        opened = await call_json(
                            "tabs",
                            {
                                "action": "open",
                                "url": "data:text/html,<title>Compact Tab</title>",
                            },
                        )
                        switched = await call_json(
                            "tabs",
                            {"action": "switch", "handle": tab_state["active_handle"]},
                        )
                        closed = await call_json(
                            "tabs", {"action": "close", "handle": opened["handle"]}
                        )
                        self.assertEqual(tab_state["active_handle"], switched["handle"])
                        self.assertNotIn(opened["handle"], closed["remaining_handles"])

                        viewport = await call_json(
                            "take_screenshot",
                            {
                                "file_name": "compact-viewport",
                                "directory": str(screenshot_directory),
                                "mode": "viewport",
                            },
                        )
                        full_page = await call_json(
                            "take_screenshot",
                            {
                                "file_name": "compact-full-page",
                                "directory": str(screenshot_directory),
                                "mode": "full_page",
                            },
                        )
                        element_shot = await call_json(
                            "take_screenshot",
                            {
                                "file_name": "compact-title",
                                "directory": str(screenshot_directory),
                                "mode": "element",
                                "element_ref": title_ref,
                            },
                        )
                        self.assertTrue(
                            all(item["ok"] for item in (viewport, full_page, element_shot))
                        )
                        for item in (viewport, full_page, element_shot):
                            self.assertTrue(Path(item["path"]).is_file())
                        viewport_bytes = Path(viewport["path"]).read_bytes()
                        full_bytes = Path(full_page["path"]).read_bytes()
                        viewport_size = struct.unpack(">II", viewport_bytes[16:24])
                        full_size = struct.unpack(">II", full_bytes[16:24])
                        self.assertGreater(full_size[1], viewport_size[1])

                        download_ref = await query_ref(
                            {"type": "css", "value": "#download-link"}
                        )
                        download_click = await call_json(
                            "interact_element",
                            {"action": "click", "element_ref": download_ref},
                        )
                        self.assertTrue(download_click["ok"])
                        downloaded_file = download_path / "e2e-download.txt"
                        for _ in range(50):
                            if downloaded_file.is_file():
                                break
                            await asyncio.sleep(0.1)
                        self.assertEqual(
                            "selenium compact download\n",
                            downloaded_file.read_text(),
                        )

                        reload_result = await call_json(
                            "navigate",
                            {
                                "url": fixture_url + "?reload=stale",
                                "wait_until": "complete",
                                "timeout": 10,
                            },
                        )
                        self.assertTrue(reload_result["ok"])
                        stale = await call_json(
                            "interact_element",
                            {"action": "click", "element_ref": title_ref},
                        )
                        self.assertEqual("stale_element_ref", stale["error"]["code"])
            finally:
                NormalChromeDriver(
                    user_data_dir=str(profile_path)
                )._kill_chrome_with_user_data_dir()
                http_server.shutdown()
                http_server.server_close()
                http_thread.join(timeout=5)

    def test_legacy_and_compact_profiles_over_stdio(self) -> None:
        with self.subTest(profile="legacy-explicit"):
            asyncio.run(self._run_workflow())
        with self.subTest(profile="compact-default"):
            asyncio.run(self._run_compact_workflow())


if __name__ == "__main__":
    unittest.main()
