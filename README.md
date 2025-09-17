Selenium MCP Server
---

A Model Context Protocol (MCP) server that provides web automation capabilities through Selenium WebDriver. This server allows AI assistants to interact with web pages by providing tools for navigation, element interaction, taking screenshots, and more.

## Quick Start

### Using Installed Package (Recommended)
```bash
# Install
pip install mcp-server-selenium

# Run
python -m mcp_server_selenium --port 9222 --user_data_dir /tmp/chrome-debug
```

### Using Source Code (Development)
```bash
# Clone and setup
git clone https://github.com/PhungXuanAnh/selenium-mcp-server.git
cd selenium-mcp-server
uv sync

# Run
PYTHONPATH=src python -m mcp_server_selenium --port 9222 --user_data_dir /tmp/chrome-debug
```

---

- [1. Features](#1-features)
- [2. Available Tools](#2-available-tools)
- [3. Installation](#3-installation)
  - [3.1. Prerequisites](#31-prerequisites)
  - [3.2. Installation Options](#32-installation-options)
    - [Option A: Install as Python Package (Recommended)](#option-a-install-as-python-package-recommended)
    - [Option B: Run from Source Code](#option-b-run-from-source-code)
  - [3.3. Chrome Setup](#33-chrome-setup)
- [4. Usage](#4-usage)
  - [4.1. Running the MCP Server](#41-running-the-mcp-server)
    - [Option A: From Installed Package](#option-a-from-installed-package)
    - [Option B: From Source Code](#option-b-from-source-code)
  - [4.2. Using MCP Inspector for Testing](#42-using-mcp-inspector-for-testing)
    - [4.2.1. Start Inspector Server](#421-start-inspector-server)
    - [4.2.2. Access Inspector Interface](#422-access-inspector-interface)
    - [4.2.3. Command Line Options](#423-command-line-options)
  - [4.3. Using with MCP Clients](#43-using-with-mcp-clients)
    - [4.3.1. Configuration Examples](#431-configuration-examples)
    - [Debug](#debug)
- [5. Examples](#5-examples)
  - [5.1. Basic Web Automation](#51-basic-web-automation)
  - [5.2. Advanced Usage](#52-advanced-usage)
- [6. Logging](#6-logging)
- [7. Troubleshooting](#7-troubleshooting)
  - [7.1. Common Issues](#71-common-issues)
    - [Installation-Related Issues](#installation-related-issues)
    - [Runtime Issues](#runtime-issues)
    - [Configuration Issues](#configuration-issues)
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

## 3.2. Installation Options

You can use this MCP server in two ways:

### Option A: Install as Python Package (Recommended)

Install directly from PyPI:
```bash
pip install mcp-server-selenium
```

Or using uv:
```bash
uv add mcp-server-selenium
```

### Option B: Run from Source Code

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

## 3.3. Chrome Setup

The MCP server can work with Chrome in two ways:

1. **Connect to existing Chrome instance** (recommended): Start Chrome with debugging enabled:
```bash
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug
```

2. **Auto-start Chrome**: The server can automatically start Chrome if no instance is found.

# 4. Usage

## 4.1. Running the MCP Server

### Option A: From Installed Package

After installing via pip/uv, you can run the server directly:

```bash
# Basic usage with default settings
python -m mcp_server_selenium

# With custom Chrome debugging port and user data directory
python -m mcp_server_selenium --port 9222 --user_data_dir /tmp/chrome-debug

# With verbose logging
python -m mcp_server_selenium --port 9222 --user_data_dir /tmp/chrome-debug -v

# Using the installed command (if available)
selenium-mcp-server --port 9222 --user_data_dir /tmp/chrome-debug -v
```

### Option B: From Source Code

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

## 4.2. Using MCP Inspector for Testing

### 4.2.1. Start Inspector Server

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

### 4.2.2. Access Inspector Interface

Open your browser and navigate to: http://127.0.0.1:6274/#tools

![](/images/image.png)

Check logs:
```shell
tailf /tmp/selenium-mcp.log
```

### 4.2.3. Command Line Options

- `--port`: Chrome remote debugging port (default: 9222)
- `--user_data_dir`: Chrome user data directory (default: auto-generated in /tmp)
- `-v, --verbose`: Increase verbosity (use multiple times for more details)

## 4.3. Using with MCP Clients

The server communicates via stdio and follows the Model Context Protocol specification. You can integrate it with MCP-compatible AI assistants or clients.

### 4.3.1. Configuration Examples

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

### Debug

**VS Code Copilot MCP Status:**
If you open the `.vscode/mcp.json` file, you can see the MCP server status at the bottom of VS Code.

![alt text](images/image1.png)

**View MCP Logs:**
- In VS Code: Open Command Palette → "Developer: Show Logs..." → "MCP: selenium"
- Check log file: `tail -f /tmp/selenium-mcp.log`

**Common Debug Commands:**

For installed package:
```bash
# Test if package is installed correctly
python -c "import mcp_server_selenium; print('Package imported successfully')"

# Run with maximum verbosity
python -m mcp_server_selenium --port 9222 --user_data_dir /tmp/test-chrome -vv
```

For source code:
```bash
# Test module import from source
cd /path/to/selenium-mcp-server
PYTHONPATH=src python -c "import mcp_server_selenium; print('Module imported successfully')"

# Run with maximum verbosity
PYTHONPATH=src python -m mcp_server_selenium --port 9222 --user_data_dir /tmp/test-chrome -vv
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

### Installation-Related Issues

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

### Runtime Issues

1. **Chrome not starting**: Ensure Chrome is installed and accessible from PATH
2. **Port conflicts**: Use a different port with `--port` option
3. **Permission errors**: Ensure the user data directory is writable
4. **Element not found**: Increase wait times or use more specific selectors

### Configuration Issues

**MCP Client Connection Problems:**
- Verify the command path is correct (use `which python` to find Python executable)
- For source code: Ensure PYTHONPATH environment variable is set
- For installed package: Ensure the package is installed in the same Python environment as the MCP client
- Check MCP client logs for detailed error messages

## 7.2. Debug Mode

**Installed Package:**
```bash
python -m mcp_server_selenium -vv --port 9222 --user_data_dir /tmp/debug-chrome
```

**Source Code:**
```bash
cd /path/to/selenium-mcp-server
PYTHONPATH=src python -m mcp_server_selenium -vv --port 9222 --user_data_dir /tmp/debug-chrome
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
