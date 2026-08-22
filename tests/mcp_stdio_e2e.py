import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp_server_selenium.drivers.normal_chrome import NormalChromeDriver


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_TOOLS = {"list_tabs", "open_tab", "switch_tab", "close_tab", "take_screenshot"}


class McpStdioE2ETest(unittest.TestCase):
    @staticmethod
    def _result_text(result) -> str:
        texts = [item.text for item in result.content if hasattr(item, "text")]
        if result.isError:
            raise AssertionError("MCP tool call failed: " + "\n".join(texts))
        return "\n".join(texts)

    async def _run_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            profile_path = temp_path / "chrome-profile"
            screenshot_path = temp_path / "screenshots" / "exact.png"
            environment = dict(os.environ, PYTHONPATH=str(PROJECT_ROOT / "src"))
            server = StdioServerParameters(
                command=sys.executable,
                args=[
                    "-m",
                    "mcp_server_selenium",
                    "--user_data_dir",
                    str(profile_path),
                ],
                env=environment,
                cwd=PROJECT_ROOT,
            )

            try:
                async with stdio_client(server) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        initialization = await session.initialize()
                        discovered_tools = {
                            tool.name: tool for tool in (await session.list_tools()).tools
                        }
                        self.assertTrue(REQUIRED_TOOLS <= discovered_tools.keys())
                        self.assertIn(
                            "exactly one active tab context", initialization.instructions or ""
                        )
                        self.assertIn(
                            "must be serialized", initialization.instructions or ""
                        )
                        for tool_name in ("list_tabs", "open_tab", "switch_tab", "close_tab"):
                            self.assertIn(
                                "same server session",
                                discovered_tools[tool_name].description or "",
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
                                "take_screenshot", {"save_path": str(screenshot_path)}
                            )
                        )

                        self.assertEqual(before["active_handle"], switched["handle"])
                        self.assertNotIn(opened["handle"], closed["remaining_handles"])
                        self.assertIn(str(screenshot_path), screenshot_result)
                        self.assertTrue(screenshot_path.is_file())
                        self.assertFalse(screenshot_path.is_dir())
            finally:
                NormalChromeDriver(user_data_dir=str(profile_path))._kill_chrome_with_user_data_dir()

    def test_multi_tab_and_screenshot_over_stdio(self) -> None:
        asyncio.run(self._run_workflow())


if __name__ == "__main__":
    unittest.main()
