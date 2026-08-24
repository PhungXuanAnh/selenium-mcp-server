import inspect
import json
from pathlib import Path
import re
import unittest
from unittest.mock import Mock, patch

from click.testing import CliRunner

import mcp_server_selenium as package
from mcp_server_selenium.server import (
    COMPACT_MCP_INSTRUCTIONS,
    MCP_INSTRUCTIONS,
    compact_mcp,
    mcp,
)


EXPECTED_LEGACY_SIGNATURES = {
    "navigate": "(url: str, timeout: int = 60) -> str",
    "list_tabs": "() -> str",
    "open_tab": "(url: Optional[str] = None) -> str",
    "switch_tab": "(handle: str) -> str",
    "close_tab": "(handle: Optional[str] = None) -> str",
    "take_screenshot": "(file_name: str, directory: str = 'tmp/selenium-screenshot') -> str",
    "check_page_ready": "(wait_seconds: int = 0) -> str",
    "get_console_logs": "(log_level: str = '') -> str",
    "get_network_logs": "(filter_url_by_text: str = '', only_errors_log: bool = False) -> str",
    "get_response": "(request_id: str) -> str",
    "local_storage_add": "(key: str, string_value: str = '', object_value: dict = {}, create_empty_string: bool = False, create_empty_object: bool = False) -> str",
    "local_storage_read": "(key: str) -> str",
    "local_storage_remove": "(key: str) -> str",
    "local_storage_read_all": "() -> str",
    "local_storage_remove_all": "() -> str",
    "get_an_element": "(text: str = '', class_name: str = '', id: str = '', attributes: dict = {}, element_type: str = '', in_iframe_id: str = '', in_iframe_name: str = '', return_html: bool = False, xpath: str = '') -> str",
    "get_direct_children": "(text: str = '', class_name: str = '', id: str = '', attributes: dict = {}, element_type: str = '', in_iframe_id: str = '', in_iframe_name: str = '', return_html: bool = False, xpath: str = '', page: int = 1, page_size: int = 5) -> str",
    "get_elements": "(text: str = '', class_name: str = '', id: str = '', attributes: dict = {}, element_type: str = '', in_iframe_id: str = '', in_iframe_name: str = '', page: int = 1, page_size: int = 3, return_html: bool = False, xpath: str = '') -> str",
    "click_to_element": "(text: str = '', class_name: str = '', id: str = '', attributes: dict = {}, element_type: str = '', in_iframe_id: str = '', in_iframe_name: str = '', element_index: int = -1, xpath: str = '') -> str",
    "set_value_to_input_element": "(text: str = '', class_name: str = '', id: str = '', attributes: dict = {}, element_type: str = '', input_value: str = '', in_iframe_id: str = '', in_iframe_name: str = '', xpath: str = '') -> str",
    "run_javascript_in_console": "(javascript_code: str) -> str",
    "run_javascript_and_get_console_output": "(javascript_code: str) -> str",
    "get_style_an_element": "(text: str = '', class_name: str = '', id: str = '', attributes: dict = {}, element_type: str = '', in_iframe_id: str = '', in_iframe_name: str = '', return_html: bool = False, xpath: str = '', all_styles: bool = True, computed_style: bool = True) -> str",
}

EXPECTED_COMPACT_TOOLS = {
    "navigate",
    "tabs",
    "take_screenshot",
    "wait_for",
    "browser_logs",
    "local_storage",
    "query_elements",
    "interact_element",
    "run_javascript",
    "get_element_style",
}

EXPECTED_COMPACT_PARAMETERS = {
    "tabs": ("action", "url", "handle"),
    "browser_logs": (
        "action",
        "mode",
        "cursor",
        "limit",
        "since_timestamp",
        "log_level",
        "filter_url_by_text",
        "only_errors_log",
        "event_type",
        "redact",
        "request_id",
        "filters",
    ),
    "local_storage": (
        "action",
        "key",
        "string_value",
        "object_value",
        "create_empty_string",
        "create_empty_object",
    ),
    "query_elements": (
        "action",
        "selector",
        "page",
        "page_size",
        "return_html",
        "options",
    ),
    "interact_element": (
        "action",
        "element_ref",
        "input_value",
        "key",
        "option_by",
        "option_value",
        "file_path",
        "timeout",
        "options",
    ),
    "navigate": ("url", "wait_until", "timeout", "quiet_ms"),
    "take_screenshot": ("file_name", "directory", "mode", "element_ref"),
    "wait_for": (
        "condition",
        "state",
        "value",
        "selector",
        "match",
        "timeout",
        "poll_interval",
        "quiet_ms",
        "options",
    ),
    "get_element_style": (
        "element_ref",
        "return_html",
        "all_styles",
        "computed_style",
    ),
    "run_javascript": ("javascript_code", "capture_console", "timeout"),
}


class ToolProfileTests(unittest.TestCase):
    def test_legacy_contract_budget_and_profile_selection(self):
        tools = mcp._tool_manager.list_tools()
        signatures = {
            tool.name: str(inspect.signature(tool.fn)) for tool in tools
        }
        records = [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.parameters,
            }
            for tool in tools
        ]

        self.assertEqual(EXPECTED_LEGACY_SIGNATURES, signatures)
        self.assertLessEqual(
            len(json.dumps(records, ensure_ascii=False, separators=(",", ":")).encode()),
            12 * 1024,
        )
        self.assertLess(len(MCP_INSTRUCTIONS), 500)

        compact_tools = compact_mcp._tool_manager.list_tools()
        compact_records = [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.parameters,
            }
            for tool in compact_tools
        ]
        self.assertEqual(EXPECTED_COMPACT_TOOLS, {tool.name for tool in compact_tools})
        self.assertEqual(
            EXPECTED_COMPACT_PARAMETERS,
            {
                tool.name: tuple(inspect.signature(tool.fn).parameters)
                for tool in compact_tools
            },
        )
        compact_payload_bytes = len(
            json.dumps(
                compact_records,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
        )
        self.assertLess(compact_payload_bytes, 12 * 1024)
        compact_by_name = {tool.name: tool for tool in compact_tools}
        guidance = {
            "tabs": ("list needs no extra field", "browser versions", "download directory"),
            "browser_logs": ("peek preserves", "consume removes", "event/cursor/time", "filters for regex/method/type/request/status", "default redaction", "response requires"),
            "local_storage": ("add requires key", "object mode wins", "read/remove require key"),
            "query_elements": ("including hidden matches", "fields support role/name", "options.scope", "ref/rerender/navigation policy"),
            "interact_element": ("inspect diagnoses", "auto-scrolls/waits/retries", "javascript are explicit", "verified contenteditable", "scroll is bounded", "execution and observed"),
            "navigate": ("wait_until=initiated", "final_url after redirects", "timeout/error state"),
            "take_screenshot": ("mode=viewport", "element mode requires", "sensitive data"),
            "wait_for": ("one-deadline waits", "network_response/all/any", "polling ignores", "cursor/route/json predicates", "peeked, not consumed"),
            "get_element_style": ("requires element_ref", "return_html=true", "independently"),
            "run_javascript": ("promises are awaited", "bounded typed envelopes", "never reads logs", "preserving older"),
        }
        for tool_name, fragments in guidance.items():
            description = compact_by_name[tool_name].description.lower()
            with self.subTest(tool=tool_name):
                for fragment in fragments:
                    self.assertIn(fragment, description)
        expected_live_examples = {
            "browser_logs": {"action": "network", "event_type": "response"},
            "wait_for": {
                "condition": "element",
                "state": "visible",
                "selector": {"type": "css", "value": "#x"},
            },
            "interact_element": {
                "action": "inspect",
                "element_ref": "el_REF",
            },
        }
        for tool_name, expected in expected_live_examples.items():
            encoded = compact_by_name[tool_name].description.split(
                "Example JSON: ", 1
            )[1]
            self.assertEqual(expected, json.loads(encoded))
        self.assertFalse(
            compact_by_name["run_javascript"].parameters["properties"][
                "capture_console"
            ]["default"]
        )
        query_schema = compact_by_name["query_elements"].parameters
        self.assertIn("discriminator", json.dumps(query_schema))
        self.assertIn(
            "discriminator", json.dumps(compact_by_name["wait_for"].parameters)
        )
        for fragment in (
            "Recommended workflow",
            "shared mutable state",
            "peek preserves entries",
            "browser versions",
            "sensitive",
        ):
            self.assertIn(fragment, COMPACT_MCP_INSTRUCTIONS)
        documentation = (
            Path(__file__).resolve().parents[1] / "README.md"
        ).read_text()
        for fragment in (
            "tabs(list) -> navigate -> wait_for -> query_elements",
            "compact profile is the default",
            "--tool-profile legacy",
            '"type":"css"',
            "tab/document change",
            'mode="peek|consume"',
            "redact=false",
            "Treat screenshots, uploads, downloads",
            "--download_dir",
        ):
            self.assertIn(fragment, documentation)
        agent_guidance = (
            Path(__file__).resolve().parents[1]
            / ".github/instructions/test-selenium-tools-directly.instructions.md"
        ).read_text()
        self.assertIn("MCP launches use the 10-name `compact` profile", agent_guidance)
        self.assertIn("default. Pass `--tool-profile legacy`", agent_guidance)
        self.assertIn("--tool-profile legacy", agent_guidance)

        examples = documentation.split(
            "### Complete compact action examples", 1
        )[1].split("# 4. Installation", 1)[0]

        def read_examples(tool_name):
            match = re.search(
                rf"#### `{tool_name}`\n\n```jsonl\n(.*?)\n```",
                examples,
                re.DOTALL,
            )
            self.assertIsNotNone(match, tool_name)
            return [json.loads(line) for line in match.group(1).splitlines()]

        expected_variants = {
            "tabs": ("action", {"list", "open", "switch", "close"}),
            "navigate": (
                "wait_until",
                {"initiated", "interactive", "complete", "network_idle"},
            ),
            "wait_for": (
                "condition",
                {
                    "ready", "url", "element", "text", "network_idle",
                    "network_response", "all", "any",
                },
            ),
            "query_elements": ("action", {"one", "many", "children"}),
            "interact_element": (
                "action",
                {
                    "inspect", "scroll", "click", "clear", "type", "set_value", "press_key",
                    "select_option", "hover", "scroll_into_view", "upload_file",
                },
            ),
            "take_screenshot": ("mode", {"viewport", "full_page", "element"}),
            "browser_logs": ("action", {"console", "network", "response"}),
            "local_storage": (
                "action", {"add", "read", "remove", "read_all", "remove_all"},
            ),
        }
        for tool_name, (field, values) in expected_variants.items():
            self.assertEqual(values, {item[field] for item in read_examples(tool_name)})
        self.assertTrue(read_examples("get_element_style"))
        self.assertTrue(read_examples("run_javascript"))

        runner = CliRunner()
        with (
            patch.object(package.server, "debug_port", 0),
            patch.object(package.server, "find_available_port", return_value=23456),
            patch.object(package.server, "get_driver_factory"),
            patch.object(package.server, "initialize_driver_instance") as initialize,
            patch.object(package.server, "configure_download_directory"),
            patch.object(package, "quit_driver"),
            patch.object(mcp, "run") as legacy_run,
            patch.object(compact_mcp, "run") as compact_run,
        ):
            initialize.return_value.ensure_driver_initialized = Mock()
            default_result = runner.invoke(package.main, [])
            legacy_result = runner.invoke(
                package.main, ["--tool-profile", "legacy"]
            )

        self.assertEqual(0, default_result.exit_code, default_result.output)
        self.assertEqual(0, legacy_result.exit_code, legacy_result.output)
        legacy_run.assert_called_once_with(transport="stdio")
        compact_run.assert_called_once_with(transport="stdio")


if __name__ == "__main__":
    unittest.main()
