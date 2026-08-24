Selenium MCP Server
---

[![Available on CodeGuilds](https://img.shields.io/badge/Available_on-CodeGuilds-6366f1)](https://codeguilds.dev/packages/selenium-mcp-server)

[![Listed on awesome-remote-mcp-servers](https://img.shields.io/badge/Listed_on-awesome--remote--mcp--servers-blue?logo=github)](https://github.com/Appnova-EU-OU/awesome-remote-mcp-servers)

A Model Context Protocol (MCP) server that provides web automation capabilities through Selenium WebDriver. This server allows AI assistants to interact with web pages by providing tools for navigation, element interaction, taking screenshots, and more.

## 1.1. Quick Start

### 1.1.1. Using Installed Package (Recommended)
```bash
# Install
pip install mcp-server-selenium

# Run
python -m mcp_server_selenium --port 9222 --user_data_dir /tmp/chrome-debug
```

### 1.1.2. Using Source Code (Development)
```bash
# Clone and setup
git clone https://github.com/PhungXuanAnh/selenium-mcp-server.git
cd selenium-mcp-server
uv sync

# Run
PYTHONPATH=src python -m mcp_server_selenium --port 9222 --user_data_dir /tmp/chrome-debug
```

---

- [2. Features](#2-features)
- [3. Available Tools](#3-available-tools)
  - [3.1. Navigation and Page Management](#31-navigation-and-page-management)
  - [3.2. Element Interaction](#32-element-interaction)
  - [3.3. Element Styling](#33-element-styling)
  - [3.4. JavaScript Execution](#34-javascript-execution)
  - [3.5. Browser Logs](#35-browser-logs)
  - [3.6. Local Storage Management](#36-local-storage-management)
- [4. Installation](#4-installation)
  - [4.1. Prerequisites](#41-prerequisites)
  - [4.2. Installation Options](#42-installation-options)
    - [4.2.1. Option A: Install as Python Package (Recommended)](#421-option-a-install-as-python-package-recommended)
    - [4.2.2. Option B: Run from Source Code](#422-option-b-run-from-source-code)
  - [4.3. Chrome Setup](#43-chrome-setup)
- [5. Usage](#5-usage)
  - [5.1. Running the MCP Server](#51-running-the-mcp-server)
    - [5.1.1. Option A: From Installed Package](#511-option-a-from-installed-package)
    - [5.1.2. Option B: From Source Code](#512-option-b-from-source-code)
  - [5.2. Using MCP Inspector for Testing](#52-using-mcp-inspector-for-testing)
    - [5.2.1. Start Inspector Server](#521-start-inspector-server)
    - [5.2.2. Access Inspector Interface](#522-access-inspector-interface)
    - [5.2.3. Command Line Options](#523-command-line-options)
  - [5.3. Using with MCP Clients](#53-using-with-mcp-clients)
    - [5.3.1. Configuration Examples](#531-configuration-examples)
    - [5.3.2. Debug](#532-debug)
- [6. Examples](#6-examples)
  - [6.1. Basic Web Automation](#61-basic-web-automation)
  - [6.2. Advanced Usage](#62-advanced-usage)
    - [6.2.1. JavaScript Examples](#621-javascript-examples)
- [7. Logging](#7-logging)
- [8. Troubleshooting](#8-troubleshooting)
  - [8.1. Common Issues](#81-common-issues)
    - [8.1.1. Installation-Related Issues](#811-installation-related-issues)
    - [8.1.2. Runtime Issues](#812-runtime-issues)
    - [8.1.3. Configuration Issues](#813-configuration-issues)
- [9. Architecture](#9-architecture)
- [10. Contributing](#10-contributing)
- [11. Support](#11-support)
- [12. Documentation](#12-documentation)
- [13. Reference](#13-reference)


# 2. Features

- **Web Navigation**: Navigate to URLs with timeout control and page readiness checking
- **Multiple Tabs**: List, open, switch, and close browser tabs by window handle
- **Element Discovery & Interaction**: Find elements by multiple criteria (text, class, ID, attributes, XPath) and interact with them through clicking and input value setting
- **Advanced Element Querying**: Get single elements, multiple elements with pagination, and direct child nodes with comprehensive filtering options
- **Screenshots**: Capture named PNG screenshots of the active tab in the default workspace location or an explicit output directory
- **Element Styling**: Retrieve CSS styles and computed style information for any element
- **JavaScript Execution**: Execute custom JavaScript code in browser console with optional console output capture
- **Browser Logging**: Access console logs (with level filtering) and network request logs (with URL filtering and error filtering)
- **Local Storage Management**: Complete CRUD operations for browser local storage (add, read, update, delete)
- **iFrame Support**: Work with elements inside iframes using iframe ID or name targeting
- **XPath Support**: Use XPath expressions for precise element targeting
- **Chrome Browser Control**: Connect to existing Chrome instances or automatically start new ones

# 3. Available Tools

The default `compact` profile is documented in [Compact Profile (Default)](#37-compact-profile-default).
The explicit `--tool-profile legacy` compatibility fallback provides the following 23
tools with their original names and call contracts.

## 3.1. Navigation and Page Management
- `navigate(url, timeout)` - Navigate to a specified URL with Chrome browser
- `check_page_ready(wait_seconds)` - Check if the current page is fully loaded with optional wait
- `list_tabs()` - List all browser tabs and identify the active tab
- `open_tab(url=None)` - Open a new tab and optionally navigate it to a URL
- `switch_tab(handle)` - Switch to a tab using a handle returned by `list_tabs`
- `close_tab(handle=None)` - Close a specific tab, or the active tab when no handle is provided
- `take_screenshot(file_name, directory="tmp/selenium-screenshot")` - Take a screenshot of the active tab. A descriptive `file_name` is required; `.png` is added when omitted. When the Agent knows its current workspace path, it should prefer an absolute `directory` inside that workspace so the destination does not depend on the MCP server cwd. Otherwise, omit `directory` to use the configured workspace default. Existing files receive a numeric suffix instead of being overwritten.

## 3.2. Element Interaction
- `get_an_element(text, class_name, id, attributes, element_type, in_iframe_id, in_iframe_name, return_html, xpath)` - Get an element identified by various criteria
- `get_elements(text, class_name, id, attributes, element_type, in_iframe_id, in_iframe_name, page, page_size, return_html, xpath)` - Get multiple elements with pagination support
- `get_direct_children(text, class_name, id, attributes, element_type, in_iframe_id, in_iframe_name, return_html, xpath, page, page_size)` - Get all direct child nodes of an element with pagination
- `click_to_element(text, class_name, id, attributes, element_type, in_iframe_id, in_iframe_name, element_index, xpath)` - Click on an element identified by various criteria
- `set_value_to_input_element(text, class_name, id, attributes, element_type, input_value, in_iframe_id, in_iframe_name, xpath)` - Set a value to an input element

## 3.3. Element Styling
- `get_style_an_element(text, class_name, id, attributes, element_type, in_iframe_id, in_iframe_name, return_html, xpath, all_styles, computed_style)` - Get style information for an element

## 3.4. JavaScript Execution
- `run_javascript_in_console(javascript_code)` - Execute JavaScript without intentionally reading buffered console logs
- `run_javascript_and_get_console_output(javascript_code)` - Drain old console logs, execute JavaScript, then return its value and newly captured console output

## 3.5. Browser Logs
- `get_console_logs(log_level)` - Read and consume browser console logs with optional level filtering
- `get_network_logs(filter_url_by_text, only_errors_log)` - Read and consume performance logs as network events with optional filtering
- `get_response(request_id)` - Retrieve a response body using a request ID from `get_network_logs`

## 3.6. Local Storage Management
- `local_storage_add(key, string_value, object_value, create_empty_string, create_empty_object)` - Add or update a key-value pair in browser's local storage
- `local_storage_read(key)` - Read a value from browser's local storage by key
- `local_storage_read_all()` - Read all key-value pairs from browser's local storage
- `local_storage_remove(key)` - Remove a key-value pair from browser's local storage
- `local_storage_remove_all()` - Remove all key-value pairs from browser's local storage

## 3.7. Compact Profile (Default)

The compact profile is the default and exposes the same browser capabilities through 10
tools and a smaller `tools/list` payload. It remains under evaluation; use
`--tool-profile legacy` when an existing client still depends on the original 23 names.
Legacy removal, if ever planned, will be announced as a separate breaking lifecycle
change. Legacy names are not advertised as compact aliases because aliases would keep
their schemas in Agent context.

Start it with:

```bash
python -m mcp_server_selenium

# Explicit compatibility fallback
python -m mcp_server_selenium --tool-profile legacy
```

All compact calls share one browser session and global active tab. A reliable default
workflow is:

```text
tabs(list) -> navigate -> wait_for -> query_elements -> interact_element -> take_screenshot
```

Use only fields relevant to an action. The 23 legacy names map to compact as follows:

| Legacy tool | Compact call |
|---|---|
| `navigate(url, timeout)` | `navigate(url, wait_until="complete", timeout=timeout)` |
| `list_tabs()` | `tabs(action="list")` |
| `open_tab(url)` | `tabs(action="open", url=url)` |
| `switch_tab(handle)` | `tabs(action="switch", handle=handle)` |
| `close_tab(handle)` | `tabs(action="close", handle=handle)` |
| `take_screenshot(file_name, directory)` | `take_screenshot(file_name, directory, mode="viewport")` |
| `check_page_ready(wait_seconds)` | `wait_for(condition="ready", state="complete")` |
| `get_console_logs(log_level)` | `browser_logs(action="console", log_level=log_level)` |
| `get_network_logs(filter_url_by_text, only_errors_log)` | `browser_logs(action="network", filter_url_by_text=..., only_errors_log=...)` |
| `get_response(request_id)` | `browser_logs(action="response", request_id=request_id)` |
| `local_storage_add(...)` | `local_storage(action="add", key=..., string_value=... or object_value=...)` |
| `local_storage_read(key)` | `local_storage(action="read", key=key)` |
| `local_storage_remove(key)` | `local_storage(action="remove", key=key)` |
| `local_storage_read_all()` | `local_storage(action="read_all")` |
| `local_storage_remove_all()` | `local_storage(action="remove_all")` |
| `get_an_element(...)` | `query_elements(action="one", selector=...)` |
| `get_elements(...)` | `query_elements(action="many", selector=...)` |
| `get_direct_children(...)` | `query_elements(action="children", selector=...)` |
| `click_to_element(...)` | Query, then `interact_element(action="click", element_ref=...)` |
| `set_value_to_input_element(...)` | Query, then `interact_element(action="set_value", element_ref=..., input_value=...)` |
| `run_javascript_in_console(javascript_code)` | `run_javascript(javascript_code)` |
| `run_javascript_and_get_console_output(javascript_code)` | `run_javascript(javascript_code, capture_console=true)` |
| `get_style_an_element(...)` | Query, then `get_element_style(element_ref=...)` |

### Compact quick example

Each line is one JSON arguments object for the workflow step in the same order:

```jsonl
{"action":"list"}
{"url":"https://example.com","wait_until":"network_idle","timeout":30,"quiet_ms":500}
{"condition":"element","state":"visible","selector":{"type":"css","value":"#login"},"timeout":10}
{"action":"one","selector":{"type":"css","value":"#login"}}
{"action":"click","element_ref":"el_VALUE_FROM_QUERY"}
{"file_name":"login-result","mode":"full_page"}
```

`tabs(action="list")` also reports the active handle, URL/title/`readyState` of every
tab, Chrome and ChromeDriver versions, and the absolute download directory. `open`
activates its new tab; `switch` requires a listed handle; `close` accepts a handle or the
active tab but never the final tab. Serialize tab-sensitive calls.

### Selectors, waits, and references

`query_elements` and element/text `wait_for` accept one discriminated selector:

```jsonl
{"type":"xpath","value":"//button[@type='submit']"}
{"type":"css","value":"form.login button.primary","frame":"payment-frame"}
{"type":"fields","value":{"element_type":"input","id":"email","attribute:data-test":"login-email"}}
{"type":"fields","value":{"element_type":"article","role":"article","accessible_name":"Assistant message"}}
{"type":"ref","value":"el_VALUE_FROM_QUERY"}
```

Fields combine with AND; `role` and `accessible_name` use Selenium's computed
accessibility values. `frame` tries iframe ID, then name. For ordered nested traversal,
use up to eight `options.scope` steps; frame steps support CSS/ID/name and shadow steps
enter open shadow roots:

```json
{"action":"one","selector":{"type":"css","value":"button.allow"},"options":{"scope":[{"type":"frame","value":"payment-frame","by":"id"},{"type":"shadow","value":"#permission-host","by":"css"}]}}
```

XPath is supported in documents/frames; use CSS or fields inside shadow roots. Query
pages are 1-based;
the default sizes are 3 for `many` and 5 for `children`, with a maximum of 50. `one`
requires exactly one match and `children` exactly one parent. Every result element has an
opaque `element_ref`. Queries include hidden DOM matches and report `visible` separately.
Refs store locator specifications, not WebElements, and re-resolve after same-document
rerenders while the exact locator still matches one element. They expire after 1,800
seconds and become invalid after a tab/document change, full navigation, or a zero/multiple
current match; query again in those cases.

`wait_for.condition` supports:

| Condition | Required/action fields |
|---|---|
| `ready` | `state="interactive|complete"` |
| `url` | `value`, optional `match="contains|equals|regex"` |
| `element` | `selector`, `state="present|visible|enabled|hidden"` |
| `text` | `value`, optional `selector`, `state="present|absent"` and `match` |
| `network_idle` | optional `quiet_ms`; `options.ignore_url_regexes` excludes known polling routes |
| `network_response` | `options.cursor`, route `filters`, and optional dotted-path `json_predicate` |
| `all`, `any` | `options.conditions`, 1-10 bounded nested clauses with one shared deadline |

For a selector-free text wait, the observed value is the complete
`document.body.innerText`. With a selector, it is every matched element's `.text` joined
with newline characters. Therefore `match="equals"` compares that entire exact string,
including browser-produced whitespace and newlines; use `contains` for a fragment.

Network-response waits peek without consuming diagnostic events. Take a baseline
`latest_cursor` from `browser_logs`, trigger the request, then wait after that cursor:

```json
{"condition":"network_response","timeout":30,"options":{"cursor":120,"filters":{"url_regex":"/api/build(?:\\?|$)","method":"GET","resource_type":"Fetch","status":200},"json_predicate":{"partial":false}}}
```

`network_idle` ignores long-lived EventSource/WebSocket requests but normal polling creates
fresh finite requests; declare only known polling routes in `ignore_url_regexes` or prefer
`network_response`. `timeout` is the deadline for the complete tool call/composed wait,
not for each poll or clause. `timeout` and `poll_interval` are seconds; `quiet_ms` is
milliseconds. Success and
timeout responses include elapsed time, URL, ready state, and the last observation.
`navigate.wait_until` accepts `initiated`, `interactive`, `complete`, or `network_idle`;
completed policies return the final URL after redirects, while `initiated` explicitly
reports that navigation remains pending.

### Interactions, actionability, style, and artifacts

All actions except viewport/nested `scroll` require `element_ref`. Action-specific fields are:

| Action | Additional fields |
|---|---|
| `inspect` | none; returns CSS/geometry/hit-test/blocker/inert/animation/scroll-ancestor diagnostics |
| `click` | optional `options.click_mode="native|actions|javascript"`, `offset`, `stability_ms`, `observe_ms` |
| `clear`, `hover`, `scroll_into_view` | none |
| `type`, `set_value` | `input_value`; options for target/input mode, clear, synthetic paste input type, verification |
| `press_key` | `key`, for example `ENTER`, `TAB`, or `ARROW_DOWN` |
| `select_option` | `option_by="value|text|index"`, `option_value` |
| `upload_file` | existing absolute or workspace-relative `file_path` |
| `scroll` | optional container ref; direction/amount/start/end, `until_visible`, nested sweep and step budget in `options` |

Click defaults to WebDriver native click. It re-resolves the ref, centers it, waits for a
stable actionable hit-test, and retries stale/intercepted/temporarily non-interactable
states within the one overall timeout. Failure reports the covering element and reasons
such as hidden, offscreen, inert, animation, or `pointer-events:none`. Actions/offset and
DOM JavaScript click are explicit choices; JavaScript is never a silent fallback.

`type` appends by default and `set_value` replaces. `target_kind="auto|form_control|contenteditable"`
and `input_mode="auto|keyboard|dom"` support inputs, textareas, and ProseMirror-style
contenteditable roots. DOM rich-text insertion dispatches cancelable `beforeinput`, then
`input`/`change`; `input_type="insertFromPaste"` supplies synthetic paste semantics without
reading or changing the system clipboard. Verification is on by default and compares
`.value` or rendered editor text; a mismatch returns `input_postcondition_failed`.

`ok=true` means the requested browser command completed and any declared postcondition
passed. It does not assert application intent. `execution` reports the actual strategy and
reported events; `observed` separately reports URL, target state, focus/selection, bounded
DOM mutations, `effect_observed`, and always `application_outcome="not_asserted"`.

`scroll` is server-controlled rather than a long-running page loop. It can operate on one
container ref or scan bounded nested containers, stop when a selector/ref is truly visible
by viewport hit-test, and use `direction="both"` for a down-then-up sweep.

`get_element_style(element_ref, ...)` requires one ref. `return_html=true` returns only
bounded inner/outer HTML and overrides the style flags. Otherwise `all_styles` and
`computed_style` independently add their bounded sections; both false returns element
metadata only.

Screenshots use `mode="viewport|full_page|element"`; element mode requires a ref. Names
are safe PNG basenames and collisions get numeric suffixes. Directories may be absolute
or workspace-relative without traversal. Chrome downloads default to
`<workspace>/tmp/selenium-downloads`; configure them with `--download_dir`.

### Logs, JavaScript, storage, and sensitive data

Console/network log calls accept `mode="peek|consume"`, `cursor`, `limit` (1-100), and
`since_timestamp` (epoch milliseconds). `peek` preserves returned entries; `consume`
removes them. Continue with `next_cursor`. Buffers and cursors are browser-session local
and bounded. Console levels are blank/`ALL`, `DEBUG`, `INFO`, `WARNING`, `ERROR`, or
`SEVERE` (`ERROR` aliases Chrome `SEVERE`). Network `filters` support URL regex, HTTP
method, resource type, request ID, and status in addition to legacy URL-text/error filters.
Correlated metadata lets response/finished events filter on original request properties.
Redaction is on by default for credentials, sensitive query values, and request
body/header text; `redact=false` is an explicit sensitive-data opt-in.

```jsonl
{"action":"console","mode":"peek","cursor":0,"limit":20,"log_level":"ERROR"}
{"action":"network","mode":"consume","cursor":0,"limit":50,"filter_url_by_text":"/api/","redact":true}
{"action":"network","mode":"peek","event_type":"response","filters":{"url_regex":"/api/build","method":"GET","resource_type":"Fetch","status":200},"redact":true}
{"action":"response","request_id":"CDP_REQUEST_ID"}
```

Response bodies can expire or be evicted from Chrome's CDP buffer; error envelopes give a
stable reason code and retry hint. Bodies themselves may contain sensitive data.

`run_javascript` awaits Promises and returns bounded typed values for `undefined`, `null`,
primitives, DOM elements, arrays/objects, circular/max-depth values, and exceptions.
`capture_console=false` never reads logs. `true` returns only newly generated entries and
keeps older entries in the broker. Example:

```json
{"javascript_code":"return await Promise.resolve(document.querySelector('h1'))","capture_console":false,"timeout":30}
```

Storage `add` requires `key` plus a value or explicit empty-value flag; object mode wins
over string mode. `read`/`remove` require `key`; `read_all`/`remove_all` need no extra
field. localStorage is scoped to the active page origin.

Treat screenshots, uploads, downloads, response bodies, raw logs, tabs, and localStorage
as potentially sensitive. They can contain credentials, PHI, or data from another origin
in the shared session. Use explicit artifact paths and `redact=false` only when authorized.

### Complete compact action examples

Each line below is one complete JSON arguments object for the named tool. Replace handle,
reference, request-ID, path, URL, and expected-text placeholders with observed values.

#### `tabs`

```jsonl
{"action":"list"}
{"action":"open","url":"https://example.com"}
{"action":"switch","handle":"TAB_HANDLE_FROM_LIST"}
{"action":"close","handle":"TAB_HANDLE_FROM_LIST"}
```

#### `navigate`

```jsonl
{"url":"https://example.com","wait_until":"initiated","timeout":30}
{"url":"https://example.com","wait_until":"interactive","timeout":30}
{"url":"https://example.com","wait_until":"complete","timeout":30}
{"url":"https://example.com","wait_until":"network_idle","timeout":30,"quiet_ms":500}
```

#### `wait_for`

```jsonl
{"condition":"ready","state":"complete","timeout":10}
{"condition":"url","value":"/dashboard","match":"contains","timeout":10}
{"condition":"element","state":"visible","selector":{"type":"css","value":"#login"},"timeout":10}
{"condition":"text","state":"present","value":"Welcome","selector":{"type":"css","value":"main"},"match":"contains","timeout":10}
{"condition":"network_idle","quiet_ms":500,"timeout":10}
{"condition":"network_idle","quiet_ms":500,"timeout":10,"options":{"ignore_url_regexes":["/api/poll(?:\\?|$)"]}}
{"condition":"network_response","timeout":30,"options":{"cursor":120,"filters":{"url_regex":"/api/build","method":"GET","status":200},"json_predicate":{"partial":false}}}
{"condition":"all","timeout":30,"options":{"conditions":[{"condition":"element","state":"visible","selector":{"type":"css","value":"main"}},{"condition":"network_response","options":{"cursor":120,"filters":{"url_regex":"/api/build"}}}]}}
{"condition":"any","timeout":30,"options":{"conditions":[{"condition":"text","state":"present","value":"Done"},{"condition":"url","value":"/complete"}]}}
```

#### `query_elements`

```jsonl
{"action":"one","selector":{"type":"css","value":"#login"}}
{"action":"many","selector":{"type":"fields","value":{"element_type":"button"}},"page":1,"page_size":10}
{"action":"children","selector":{"type":"ref","value":"el_PARENT_FROM_QUERY"},"page":1,"page_size":10}
{"action":"one","selector":{"type":"fields","value":{"element_type":"article","role":"article","accessible_name":"Assistant message"}}}
{"action":"one","selector":{"type":"css","value":"button.allow"},"options":{"scope":[{"type":"frame","value":"app-frame","by":"id"},{"type":"shadow","value":"#gate-host"}]}}
```

#### `interact_element`

```jsonl
{"action":"inspect","element_ref":"el_FROM_QUERY"}
{"action":"click","element_ref":"el_FROM_QUERY"}
{"action":"click","element_ref":"el_FROM_QUERY","options":{"click_mode":"actions","offset":{"x":0,"y":0},"stability_ms":100}}
{"action":"click","element_ref":"el_FROM_QUERY","options":{"click_mode":"javascript"}}
{"action":"clear","element_ref":"el_FROM_QUERY"}
{"action":"type","element_ref":"el_FROM_QUERY","input_value":"hello"}
{"action":"set_value","element_ref":"el_FROM_QUERY","input_value":"hello"}
{"action":"set_value","element_ref":"el_FROM_QUERY","input_value":"hello","options":{"target_kind":"contenteditable","input_mode":"auto","clear_existing":true,"verify_after_input":true}}
{"action":"press_key","element_ref":"el_FROM_QUERY","key":"ENTER"}
{"action":"select_option","element_ref":"el_FROM_QUERY","option_by":"value","option_value":"active"}
{"action":"hover","element_ref":"el_FROM_QUERY"}
{"action":"scroll_into_view","element_ref":"el_FROM_QUERY"}
{"action":"scroll","element_ref":"el_SCROLL_CONTAINER","timeout":10,"options":{"direction":"down","amount":400,"until_visible":{"type":"ref","value":"el_TARGET"},"max_steps":20}}
{"action":"scroll","timeout":10,"options":{"direction":"both","amount":500,"until_visible":{"type":"css","value":"button.allow"},"include_nested_scroll_containers":true,"max_steps":30}}
{"action":"upload_file","element_ref":"el_FROM_QUERY","file_path":"/absolute/path/to/file.txt"}
```

#### `take_screenshot`

```jsonl
{"file_name":"page","mode":"viewport"}
{"file_name":"full-page","mode":"full_page"}
{"file_name":"component","mode":"element","element_ref":"el_FROM_QUERY"}
```

#### `browser_logs`

```jsonl
{"action":"console","mode":"peek","cursor":0,"limit":20,"log_level":"ERROR"}
{"action":"network","mode":"peek","cursor":0,"limit":20,"event_type":"response","filter_url_by_text":"/api/","redact":true}
{"action":"network","mode":"peek","event_type":"response","filters":{"url_regex":"/api/build","method":"GET","resource_type":"Fetch","status":200},"redact":true}
{"action":"response","request_id":"CDP_REQUEST_ID"}
```

#### `local_storage`

```jsonl
{"action":"add","key":"settings","object_value":{"theme":"dark"}}
{"action":"read","key":"settings"}
{"action":"remove","key":"settings"}
{"action":"read_all"}
{"action":"remove_all"}
```

#### `get_element_style`

```jsonl
{"element_ref":"el_FROM_QUERY","all_styles":false,"computed_style":false}
{"element_ref":"el_FROM_QUERY","all_styles":true,"computed_style":true}
{"element_ref":"el_FROM_QUERY","return_html":true}
```

#### `run_javascript`

```jsonl
{"javascript_code":"return document.title","capture_console":false,"timeout":30}
{"javascript_code":"console.warn('probe'); return location.href","capture_console":true,"timeout":30}
```

# 4. Installation

## 4.1. Prerequisites

- Python 3.10 or higher
- Chrome browser installed

## 4.2. Installation Options

You can use this MCP server in two ways:

### 4.2.1. Option A: Install as Python Package (Recommended)

Install directly from PyPI:
```bash
pip install mcp-server-selenium
```

Or using uv:
```bash
uv add mcp-server-selenium
```

### 4.2.2. Option B: Run from Source Code

1. Clone this repository:
```bash
git clone https://github.com/PhungXuanAnh/selenium-mcp-server.git
cd selenium-mcp-server
```

2. Install dependencies using uv:
```bash
uv sync
```

Or using pip with virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

## 4.3. Chrome Setup

The MCP server can work with Chrome in two ways:

1. **Connect to existing Chrome instance** (recommended): Start Chrome with debugging enabled:
```bash
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug
```

2. **Auto-start Chrome**: The server can automatically start Chrome if no instance is found.

# 5. Usage

## 5.1. Running the MCP Server

### 5.1.1. Option A: From Installed Package

After installing via pip/uv, you can run the server directly:

```bash
# Basic usage with the default 10-tool compact surface
python -m mcp_server_selenium

# Use the original 23 tool names for compatibility
python -m mcp_server_selenium --tool-profile legacy

# With custom Chrome debugging port and user data directory
python -m mcp_server_selenium --port 9222 --user_data_dir /tmp/chrome-debug

# With verbose logging
python -m mcp_server_selenium --port 9222 --user_data_dir /tmp/chrome-debug -v

# Using the installed command (if available)
selenium-mcp-server --port 9222 --user_data_dir /tmp/chrome-debug -v
```

### 5.1.2. Option B: From Source Code

When running from source, ensure the Python path includes the src directory:

```bash
# Navigate to the project directory
cd /path/to/selenium-mcp-server

# Activate virtual environment (if using one)
source .venv/bin/activate

# Run with proper Python path
PYTHONPATH=src python -m mcp_server_selenium --port 9222 --user_data_dir /tmp/chrome-debug -v

# Or using uv (recommended for development)
uv run python -m mcp_server_selenium --port 9222 --user_data_dir /tmp/chrome-debug -v
```

## 5.2. Using MCP Inspector for Testing

### 5.2.1. Start Inspector Server

For development and testing, you can use the MCP inspector:

**From Source Code:**
```bash
# Using uv (recommended)
uv run mcp dev src/mcp_server_selenium/__main__.py

# Or with make command
make inspector

# With custom options
uv run mcp dev src/mcp_server_selenium/__main__.py --port 9222 --user_data_dir /tmp/chrome-debug --verbose
```

**From Installed Package:**
```bash
# Create a wrapper script or use directly
mcp dev python -m mcp_server_selenium
```

### 5.2.2. Access Inspector Interface

Open your browser and navigate to: http://127.0.0.1:6274/#tools
![](/images/image.png)

Check logs:
```shell
tailf /tmp/selenium-mcp.log
```

### 5.2.3. Command Line Options

- `--port`: Chrome remote debugging port (default: 9222)
- `--user_data_dir`: Chrome user data directory (default: auto-generated in /tmp)
- `--workspace_root`: Base directory for relative screenshot directories (default: the server startup directory). It is optional; absolute screenshot directories do not use it.
- `--tool-profile`: Agent-visible tool surface: `compact` (default) or `legacy` compatibility fallback
- `--download_dir`: Chrome download directory; defaults to `<workspace_root>/tmp/selenium-downloads`
- `-v, --verbose`: Increase verbosity (use multiple times for more details)

## 5.3. Using with MCP Clients

The server communicates via stdio and follows the Model Context Protocol specification. You can integrate it with MCP-compatible AI assistants or clients.

### 5.3.1. Configuration Examples

**For Claude Desktop** (`claude_desktop_config.json`):

Using installed package:
```json
{
  "mcpServers": {
    "selenium": {
      "command": "python",
      "args": [
        "-m", "mcp_server_selenium",
        "--port", "9222",
        "--user_data_dir", "/tmp/chrome-debug-claude"
      ],
      "env": {}
    }
  }
}
```

**For VS Code Copilot** (`.vscode/mcp.json`):

Using installed package:
```json
{
  "servers": {
    "selenium-installed": {
      "command": "python",
      "args": [
        "-m", "mcp_server_selenium",
        "--user_data_dir=/home/user/.config/google-chrome-selenium-mcp",
        "--port=9225"
      ]
    }
  }
}
```

Using source code directly:
```json
{
  "servers": {
    "selenium-source": {
      "command": "/path/to/selenium-mcp-server/.venv/bin/python",
      "args": [
        "-m", "mcp_server_selenium",
        "--user_data_dir=/home/user/.config/google-chrome-selenium-mcp-source",
        "--workspace_root=/path/to/workspace",
        "--port=9226"
      ],
      "env": {
        "PYTHONPATH": "/path/to/selenium-mcp-server/src"
      }
    }
  }
}
```

Alternative source code configuration using full path:
```json
{
  "servers": {
    "selenium-source-alt": {
      "command": "/path/to/selenium-mcp-server/.venv/bin/python",
      "args": [
        "/path/to/selenium-mcp-server/src/mcp_server_selenium/__main__.py",
        "--user_data_dir=/home/user/.config/google-chrome-selenium-mcp-alt",
        "--port=9227"
      ]
    }
  }
}
```

Omit `--tool-profile` to use the default compact surface. Add `"--tool-profile",
"legacy"` to a client's server `args` only when it requires the original 23 tool names.

### 5.3.2. Debug

**VS Code Copilot MCP Status:**
If you open the `.vscode/mcp.json` file, you can see the MCP server status at the bottom of VS Code.

![alt text](images/image1.png)

**View MCP Logs:**
- In VS Code: Open Command Palette → "Developer: Show Logs..." → "MCP: selenium"
- Check log file: `tail -f /tmp/selenium-mcp.log`

# 6. Examples

## 6.1. Basic Web Automation

1. **Navigate to a website**:
   - Tool: `navigate`
   - URL: `https://example.com`

2. **Take a screenshot**:
   - Tool: `take_screenshot`
   - File name: `example-home`
   - Directory: prefer `<absolute-workspace-path>/tmp/selenium-screenshot`; omit it when the workspace path is unavailable
   - Result: Screenshot saved to `<absolute-workspace-path>/tmp/selenium-screenshot/example-home.png`

3. **Fill a form**:
   - Legacy tool: `set_value_to_input_element`
   - Arguments: `xpath="//*[@id='email']"`, `input_value="user@example.com"`

4. **Click a button**:
   - Legacy tool: `click_to_element`
   - Arguments: `xpath="//button[@type='submit']"`

5. **Execute JavaScript**:
   - Tool: `run_javascript_in_console`
   - Code: `return document.title;`
   - Result: Returns the page title

6. **JavaScript with console output**:
   - Tool: `run_javascript_and_get_console_output`
   - Code: `console.log('Hello from browser'); return window.location.href;`
   - Result: Shows both console output and return value

## 6.2. Advanced Usage

- **Check page loading**: Use `check_page_ready`; query the target again when dynamic content is expected
- **Get page information**: Use `run_javascript_in_console` with explicit return expressions
- **Element inspection**: Use `get_an_element`, `get_elements`, or `get_style_an_element`
- **JavaScript automation**: Use `run_javascript_in_console` for complex DOM manipulation and data extraction
- **JavaScript debugging**: Use `run_javascript_and_get_console_output` to capture console logs for debugging

### 6.2.1. JavaScript Examples

**Extract page data**:
```javascript
// Tool: run_javascript_in_console
var links = Array.from(document.querySelectorAll('a')).slice(0, 5).map(a => ({
    text: a.textContent.trim(),
    href: a.href
}));
return links;
```

**Page performance monitoring**:
```javascript
// Tool: run_javascript_and_get_console_output
console.time('Page Analysis');
var stats = {
    title: document.title,
    links: document.querySelectorAll('a').length,
    images: document.querySelectorAll('img').length,
    scripts: document.querySelectorAll('script').length
};
console.timeEnd('Page Analysis');
console.log('Page stats:', stats);
return stats;
```

**Form automation**:
```javascript
// Tool: run_javascript_in_console
document.querySelector('#username').value = 'testuser';
document.querySelector('#password').value = 'password123';
document.querySelector('#login-form').submit();
return 'Form submitted successfully';
```

# 7. Logging

The server logs all operations to `/tmp/selenium-mcp.log` with rotation. Use the `-v` flag to increase console verbosity:

- `-v`: INFO level logging
- `-vv`: DEBUG level logging

# 8. Troubleshooting

## 8.1. Common Issues

### 8.1.1. Installation-Related Issues

**Package not found (installed package):**
```bash
# Verify installation
pip list | grep mcp-server-selenium
# or
python -c "import mcp_server_selenium; print('OK')"
```

**Module not found (source code):**
```bash
# Ensure PYTHONPATH is set correctly
export PYTHONPATH=/path/to/selenium-mcp-server/src
# or run from project root with:
PYTHONPATH=src python -m mcp_server_selenium
```

### 8.1.2. Runtime Issues

1. **Chrome not starting**: Ensure Chrome is installed and accessible from PATH
2. **Port conflicts**: Use a different port with `--port` option
3. **Permission errors**: Ensure the user data directory is writable
4. **Element not found**: Increase wait times or use more specific selectors
5. **JavaScript execution errors**: Check browser console for syntax errors or security restrictions
6. **Console output not captured**: Ensure the JavaScript code runs successfully before checking console logs

### 8.1.3. Configuration Issues

**MCP Client Connection Problems:**
- Verify the command path is correct (use `which python` to find Python executable)
- For source code: Ensure PYTHONPATH environment variable is set
- For installed package: Ensure the package is installed in the same Python environment as the MCP client
- Check MCP client logs for detailed error messages

# 9. Architecture

- **FastMCP**: Uses the FastMCP framework for MCP protocol implementation
- **Selenium WebDriver**: Chrome WebDriver for browser automation
- **Synchronous Design**: All operations are synchronous for reliability
- **Chrome DevTools Protocol**: Connects to Chrome via remote debugging protocol

# 10. Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 10.1. Testing

Run the focused tests without starting Chrome:

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p "test_*.py" -v
```

Run the MCP stdio end-to-end test, which starts the real server and Chrome with an isolated temporary profile:

```bash
.venv/bin/python tests/mcp_stdio_e2e.py -v
```

# 11. Support

For issues and questions:
- Create an issue in the repository
- Check the logs at `/tmp/selenium-mcp.log`
- Use verbose logging for debugging

# 12. Documentation

See [Available Tools](#3-available-tools), including the complete compact migration
table, and [Examples](#6-examples).

# 13. Reference

- https://github.com/modelcontextprotocol/python-sdk
- https://github.com/modelcontextprotocol/servers
