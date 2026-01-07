# Codebase Structure

## Directory Layout
```
selenium-mcp-server/
├── src/
│   └── mcp_server_selenium/
│       ├── __init__.py         # Main entry point with CLI
│       ├── __main__.py         # Python module execution entry
│       ├── config.py           # Configuration (logging, etc.)
│       ├── server.py           # Core server logic, driver management
│       ├── drivers/            # WebDriver implementations
│       │   ├── __init__.py
│       │   ├── normal_chrome.py      # Standard ChromeDriver
│       │   └── undetected_chrome.py  # Stealth ChromeDriver
│       └── tools/              # MCP tool implementations
│           ├── __init__.py
│           ├── navigate.py           # URL navigation
│           ├── page_ready.py         # Page readiness checks
│           ├── screenshot.py         # Screenshot capture
│           ├── element_interaction.py # Element finding/interaction
│           ├── style.py              # CSS style retrieval
│           ├── script.py             # JavaScript execution
│           ├── logs.py               # Console & network logs
│           ├── local_storage.py      # Browser storage management
│           └── download.py           # Download functionality
├── .github/
│   └── instructions/           # Development instructions
├── test_call_tools_directly.py # Direct tool testing script
├── pyproject.toml              # Project configuration
├── Makefile                    # Development shortcuts
├── README.md                   # Comprehensive documentation
└── CHANGELOG.md                # Version history
```

## Key Components

### Server Module (`server.py`)
- Global driver instance management
- Driver factory pattern for multiple driver types
- Driver initialization and cleanup
- FastMCP server instance

### Tools Module
Each tool provides specific web automation functionality:
- **Navigation**: `navigate()`, `check_page_ready()`
- **Element Interaction**: `get_an_element()`, `get_elements()`, `click_to_element()`, `set_value_to_input_element()`
- **Screenshots**: `take_screenshot()`
- **Styling**: `get_style_an_element()`
- **JavaScript**: Script execution tools
- **Logging**: `get_console_logs()`, `get_network_logs()`
- **Storage**: Local storage CRUD operations

### Drivers Module
- **NormalChromeDriver**: Standard Selenium ChromeDriver
- **UndetectedChromeDriver**: Stealth driver for bot detection avoidance
