from typing import Literal, Optional

from ..server import compact_mcp, ensure_driver_initialized
from .compact_diagnostics import diagnostics_broker, response_body
from .compact_interactions import interact_json
from .compact_locator import query_json
from .compact_models import Selector
from .compact_navigation import navigate_json
from .compact_screenshot import screenshot_json
from .compact_script import run_javascript_json
from .compact_style import style_json
from .compact_tabs import list_tabs_json
from .compact_waits import wait_for_json
from .local_storage import (
    local_storage_add,
    local_storage_read,
    local_storage_read_all,
    local_storage_remove,
    local_storage_remove_all,
)
from .screenshot import (
    DEFAULT_SCREENSHOT_DIRECTORY,
)
from .tabs import close_tab, list_tabs, open_tab, switch_tab

@compact_mcp.tool(
    description="Actions: list needs no extra field and returns tab readyState, browser versions, and download directory; open accepts optional url and activates it; switch requires a listed handle; close accepts a handle or the active tab, but never the final tab. Serialize tab-sensitive calls."
)
def tabs(
    action: Literal["list", "open", "switch", "close"],
    url: Optional[str] = None,
    handle: Optional[str] = None,
) -> str:
    """Dispatch compact tab actions to the behavior-compatible legacy primitives."""
    if action == "list":
        return list_tabs_json(ensure_driver_initialized())
    if action == "open":
        return open_tab(url)
    if action == "switch":
        if not handle:
            raise ValueError("handle is required when action='switch'")
        return switch_tab(handle)
    return close_tab(handle)


@compact_mcp.tool(description='Read console/network/response evidence. peek preserves; consume removes. Network supports event/cursor/time, URL/error fields, filters for regex/method/type/request/status, and default redaction. response requires request_id. Example JSON: {"action":"network","event_type":"response"}')
def browser_logs(
    action: Literal["console", "network", "response"],
    mode: Literal["consume", "peek"] = "consume",
    cursor: int = 0,
    limit: int = 50,
    since_timestamp: int = 0,
    log_level: str = "",
    filter_url_by_text: str = "",
    only_errors_log: bool = False,
    event_type: Literal["all", "request", "response", "finished", "failed"] = "all",
    redact: bool = True,
    request_id: str = "",
    filters: dict = {},
) -> str:
    """Read diagnostics through the bounded compact-session broker."""
    import json

    driver = ensure_driver_initialized()
    try:
        if action == "console":
            if filters:
                raise ValueError("filters are supported only for network logs")
            diagnostics_broker.drain_console(driver)
            result = diagnostics_broker.read(
                "console",
                mode,
                cursor,
                limit,
                since_timestamp,
                redact,
                log_level=log_level,
            )
            return json.dumps(result, ensure_ascii=False)
        if action == "network":
            diagnostics_broker.drain_network(driver)
            result = diagnostics_broker.read(
                "network",
                mode,
                cursor,
                limit,
                since_timestamp,
                redact,
                filter_url_by_text=filter_url_by_text,
                only_errors=only_errors_log,
                event_type=event_type,
                filters=filters,
            )
            return json.dumps(result, ensure_ascii=False)
    except (RuntimeError, ValueError) as exc:
        return json.dumps(
            {"ok": False, "error": {"code": "diagnostics_error", "message": str(exc)}}
        )
    if not request_id:
        return json.dumps(
            {
                "ok": False,
                "error": {
                    "code": "request_id_required",
                    "message": "request_id is required when action='response'",
                },
            }
        )
    return json.dumps(response_body(driver, request_id), ensure_ascii=False)


@compact_mcp.tool(
    description="Actions: add requires key plus a value or explicit empty-value flag; object mode wins over string mode. read/remove require key. read_all/remove_all need no extra field. Operates on the active page's localStorage."
)
def local_storage(
    action: Literal["add", "read", "remove", "read_all", "remove_all"],
    key: str = "",
    string_value: str = "",
    object_value: dict = {},
    create_empty_string: bool = False,
    create_empty_object: bool = False,
) -> str:
    """Dispatch compact storage actions to the legacy storage primitives."""
    if action == "add":
        if not key:
            raise ValueError("key is required when action='add'")
        return local_storage_add(
            key,
            string_value,
            object_value,
            create_empty_string,
            create_empty_object,
        )
    if action == "read":
        if not key:
            raise ValueError("key is required when action='read'")
        return local_storage_read(key)
    if action == "remove":
        if not key:
            raise ValueError("key is required when action='remove'")
        return local_storage_remove(key)
    if action == "read_all":
        return local_storage_read_all()
    return local_storage_remove_all()


@compact_mcp.tool(description="Query one/many/children, including hidden matches. xpath/css/fields/ref; fields support role/name. options.scope traverses bounded frames/open shadows. Results explain 1800s ref/rerender/navigation policy.")
def query_elements(
    action: Literal["one", "many", "children"],
    selector: Selector,
    page: int = 1,
    page_size: Optional[int] = None,
    return_html: bool = False,
    options: dict = {},
) -> str:
    """Query elements through document-scoped locator specifications."""
    driver = ensure_driver_initialized()
    return query_json(driver, action, selector, page, page_size, return_html, options)


@compact_mcp.tool(description='inspect diagnoses hit-test/blockers. Native click auto-scrolls/waits/retries; actions/offset/JavaScript are explicit. Input supports verified contenteditable. scroll is bounded. timeout covers the call. execution and observed never assert app intent. Example JSON: {"action":"inspect","element_ref":"el_REF"}')
def interact_element(
    action: Literal[
        "inspect",
        "scroll",
        "click",
        "clear",
        "type",
        "set_value",
        "press_key",
        "select_option",
        "hover",
        "scroll_into_view",
        "upload_file",
    ],
    element_ref: str = "",
    input_value: str = "",
    key: str = "",
    option_by: Literal["value", "text", "index"] = "value",
    option_value: str = "",
    file_path: str = "",
    timeout: float = 10,
    options: dict = {},
) -> str:
    """Run a bounded, re-resolving interaction."""
    return interact_json(
        ensure_driver_initialized(),
        action,
        element_ref,
        input_value,
        key,
        option_by,
        option_value,
        file_path,
        timeout,
        options,
    )


@compact_mcp.tool(description="Navigate the active tab. wait_until=initiated returns while pending; interactive/complete wait for readyState; network_idle also waits quiet_ms after finite requests settle. timeout is seconds. Returns requested_url, final_url after redirects, ready_state, phases, and explicit timeout/error state.")
def navigate(
    url: str,
    wait_until: Literal["initiated", "interactive", "complete", "network_idle"] = "complete",
    timeout: float = 60,
    quiet_ms: int = 500,
) -> str:
    """Navigate with an explicit completion policy."""
    driver = ensure_driver_initialized()
    return navigate_json(driver, url, wait_until, timeout, quiet_ms)


@compact_mcp.tool(description="Capture mode=viewport, full_page, or element. Element mode requires element_ref from query_elements. file_name is a safe PNG basename; collisions get numeric suffixes. directory may be absolute or workspace-relative without traversal. Captures can contain sensitive data.")
def take_screenshot(
    file_name: str,
    directory: str = DEFAULT_SCREENSHOT_DIRECTORY,
    mode: Literal["viewport", "full_page", "element"] = "viewport",
    element_ref: str = "",
) -> str:
    """Capture a bounded browser artifact with safe naming."""
    return screenshot_json(
        ensure_driver_initialized(), file_name, directory, mode, element_ref
    )


@compact_mcp.tool(description='One-deadline waits: ready/url/element/text/network_idle/network_response/all/any. options adds polling ignores or cursor/route/JSON predicates; network evidence is peeked, not consumed. Example JSON: {"condition":"element","state":"visible","selector":{"type":"css","value":"#x"}}')
def wait_for(
    condition: Literal[
        "ready", "url", "element", "text", "network_idle", "network_response", "all", "any"
    ],
    state: str = "",
    value: str = "",
    selector: Optional[Selector] = None,
    match: Literal["contains", "equals", "regex"] = "contains",
    timeout: float = 30,
    poll_interval: float = 0.1,
    quiet_ms: int = 500,
    options: dict = {},
) -> str:
    """Wait for a concrete browser condition with a bounded deadline."""
    driver = ensure_driver_initialized()
    return wait_for_json(
        driver,
        condition,
        state,
        value,
        selector,
        match,
        timeout,
        poll_interval,
        quiet_ms,
        options,
    )


@compact_mcp.tool(description="Requires element_ref from query_elements. return_html=true returns bounded inner/outer HTML only and overrides both style flags. Otherwise all_styles and computed_style independently add bounded applied-rule and computed-property sections; both false returns element metadata only.")
def get_element_style(
    element_ref: str,
    return_html: bool = False,
    all_styles: bool = True,
    computed_style: bool = True,
) -> str:
    """Inspect one re-resolved element without repeating selector schemas."""
    return style_json(
        ensure_driver_initialized(),
        element_ref,
        return_html,
        all_styles,
        computed_style,
    )


@compact_mcp.tool(description="Execute async JavaScript in the active tab. Promises are awaited. Results use bounded typed envelopes for undefined/null, primitives, DOM elements, arrays/objects, circular/max-depth values, and exceptions. timeout is seconds. capture_console=false never reads logs; true captures only this call's new entries while preserving older broker entries.")
def run_javascript(
    javascript_code: str,
    capture_console: bool = False,
    timeout: float = 30,
) -> str:
    """Execute JavaScript with bounded serialization and optional log capture."""
    return run_javascript_json(
        ensure_driver_initialized(), javascript_code, capture_console, timeout
    )
