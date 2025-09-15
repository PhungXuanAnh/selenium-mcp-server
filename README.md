Selenium MCP Server
---

A Model Context Protocol (MCP) server that provides web automation capabilities through Selenium WebDriver. This server allows AI assistants to interact with web pages by providing tools for navigation, element interaction, taking screenshots, and more.

- [1. Features](#1-features)
- [2. Available Tools](#2-available-tools)
- [3. Installation](#3-installation)
  - [3.1. Prerequisites](#31-prerequisites)
  - [3.2. Setup](#32-setup)
  - [3.3. Chrome Setup](#33-chrome-setup)
- [4. Usage](#4-usage)
  - [4.1. Using MPC Inspector for testing](#41-using-mpc-inspector-for-testing)
    - [4.1.1. Start Inspector server](#411-start-inspector-server)
    - [4.1.2. Access inspector to test](#412-access-inspector-to-test)
    - [4.1.3. Command Line Options](#413-command-line-options)
  - [4.2. Using with MCP Clients](#42-using-with-mcp-clients)
    - [4.2.1. Configuration Example](#421-configuration-example)
    - [Debug](#debug)
- [5. Examples](#5-examples)
  - [5.1. Basic Web Automation](#51-basic-web-automation)
  - [5.2. Advanced Usage](#52-advanced-usage)
- [6. Logging](#6-logging)
- [7. Troubleshooting](#7-troubleshooting)
  - [7.1. Common Issues](#71-common-issues)
  - [7.2. Debug Mode](#72-debug-mode)
- [8. Architecture](#8-architecture)
- [9. Contributing](#9-contributing)
- [10. Support](#10-support)
- [11. Reference](#11-reference)


# 1. Features

- **Web Navigation**: Navigate to URLs and control browser navigation
- **Element Interaction**: Click buttons, fill forms, and interact with page elements
- **Screenshots**: Capture screenshots of web pages
- **Page Analysis**: Get page content, titles, and element information
- **Form Handling**: Submit forms and interact with input fields
- **Waiting Strategies**: Wait for elements to load or become clickable
- **Chrome Browser Control**: Connect to existing Chrome instances or start new ones

# 2. Available Tools

The MCP server provides the following tools:

- `navigate(url, timeout)` - Navigate to a specified URL
- `take_screenshot()` - Capture a screenshot of the current page
- `check_page_ready(wait_seconds)` - Check if the page is ready and optionally wait
- `get_page_title()` - Get the current page title
- `get_current_url()` - Get the current page URL
- `click_element(selector, by_type, wait_time)` - Click on page elements
- `fill_input(selector, text, by_type, wait_time, clear_first)` - Fill input fields
- `submit_form(selector, by_type, wait_time)` - Submit forms
- `get_element_text(selector, by_type, wait_time)` - Get text content of elements
- `get_page_content()` - Get the full page HTML content
- `scroll_page(direction, amount)` - Scroll the page
- `wait_for_element(selector, by_type, timeout, condition)` - Wait for elements
- `get_element_attribute(selector, attribute, by_type, wait_time)` - Get element attributes
- `check_element_exists(selector, by_type, wait_time)` - Check if elements exist

# 3. Installation

## 3.1. Prerequisites

- Python 3.10 or higher
- Chrome browser installed
- uv package manager

## 3.2. Setup

1. Clone this repository:
```bash
git clone <repository-url>
cd selenium-mcp-server
```

2. Install dependencies using uv:
```bash
uv sync
```

## 3.3. Chrome Setup

The MCP server can work with Chrome in two ways:

1. **Connect to existing Chrome instance** (recommended): Start Chrome with debugging enabled:
```bash
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug
```

2. **Auto-start Chrome**: The server can automatically start Chrome if no instance is found.

# 4. Usage

## 4.1. Using MPC Inspector for testing

### 4.1.1. Start Inspector server

Run the MCP server with default settings:

```bash
uv run mcp dev main.py
# or
make inspector
```

Or with custom options:
```bash
uv run mcp dev main.py --port 9222 --user_data_dir /tmp/chrome-debug --verbose
```

### 4.1.2. Access inspector to test

http://127.0.0.1:6274/#tools

![](/images/image.png)

check log:

```shell
tailf /tmp/selenium-mcp.log
```

### 4.1.3. Command Line Options

- `--port`: Chrome remote debugging port (default: 9222)
- `--user_data_dir`: Chrome user data directory (default: auto-generated in /tmp)
- `-v, --verbose`: Increase verbosity (use multiple times for more details)

## 4.2. Using with MCP Clients

The server communicates via stdio and follows the Model Context Protocol specification. You can integrate it with MCP-compatible AI assistants or clients.

### 4.2.1. Configuration Example

For Claude Desktop, add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "selenium": {
      "command": "python",
      "args": ["/path/to/selenium-mcp-server/main.py"],
      "env": {}
    }
  }
}
```

For Vscode copilot: `.vscode/mcp.json`

```json
{
  "servers": {
    "selenium": {
        "command": "/home/xuananh/repo/selenium-mcp-server/.venv/bin/python",
        "args": [
            "/home/xuananh/repo/mcp-server/src/selenium/main.py",
            "--user_data_dir=/home/xuananh/.config/google-chrome-selenium-mcp",
            "--port=9225"
        ]
    } 
  }
}
```

### Debug

In Vscode copilot, if open `.vscode/mcp.json` file, you can see mcp server status

![alt text](images/image1.png)

Or you can open command: Developer: Show logs.. > MCP: selenium to see its log

And also check log file:

```shell
tailf /tmp/selenium-mcp.log
```

# 5. Examples

## 5.1. Basic Web Automation

1. **Navigate to a website**:
   - Tool: `navigate`
   - URL: `https://example.com`

2. **Take a screenshot**:
   - Tool: `take_screenshot`
   - Result: Screenshot saved to `~/selenium-mcp/screenshot/`

3. **Fill a form**:
   - Tool: `fill_input`
   - Selector: `#email`
   - Text: `user@example.com`

4. **Click a button**:
   - Tool: `click_element`
   - Selector: `button[type="submit"]`

## 5.2. Advanced Usage

- **Wait for dynamic content**: Use `wait_for_element` to wait for elements to load
- **Get page information**: Use `get_page_title`, `get_current_url`, `get_page_content`
- **Element inspection**: Use `get_element_text`, `get_element_attribute`, `check_element_exists`

# 6. Logging

The server logs all operations to `/tmp/selenium-mcp.log` with rotation. Use the `-v` flag to increase console verbosity:

- `-v`: INFO level logging
- `-vv`: DEBUG level logging

# 7. Troubleshooting

## 7.1. Common Issues

1. **Chrome not starting**: Ensure Chrome is installed and accessible from PATH
2. **Port conflicts**: Use a different port with `--port` option
3. **Permission errors**: Ensure the user data directory is writable
4. **Element not found**: Increase wait times or use more specific selectors

## 7.2. Debug Mode

Run with maximum verbosity to see detailed logs:
```bash
python main.py -vv
```

# 8. Architecture

- **FastMCP**: Uses the FastMCP framework for MCP protocol implementation
- **Selenium WebDriver**: Chrome WebDriver for browser automation
- **Synchronous Design**: All operations are synchronous for reliability
- **Chrome DevTools Protocol**: Connects to Chrome via remote debugging protocol

# 9. Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

# 10. Support

For issues and questions:
- Create an issue in the repository
- Check the logs at `/tmp/selenium-mcp.log`
- Use verbose logging for debugging

# 11. Reference

- https://github.com/modelcontextprotocol/python-sdk
- https://github.com/modelcontextprotocol/servers
