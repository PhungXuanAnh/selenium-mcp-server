# Suggested Commands

## Development Setup

### Initial Setup
```bash
# Clone repository
git clone https://github.com/PhungXuanAnh/selenium-mcp-server.git
cd selenium-mcp-server

# Setup with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

## Running the Server

### From Source Code
```bash
# Using uv (recommended)
uv run python -m mcp_server_selenium --port 9222 --user_data_dir /tmp/chrome-debug

# Or with PYTHONPATH
PYTHONPATH=src python -m mcp_server_selenium --port 9222 --user_data_dir /tmp/chrome-debug

# With verbose logging
uv run python -m mcp_server_selenium --port 9222 --user_data_dir /tmp/chrome-debug -v
# Or double verbose for DEBUG level
uv run python -m mcp_server_selenium --port 9222 --user_data_dir /tmp/chrome-debug -vv
```

### From Installed Package
```bash
# Install
pip install mcp-server-selenium

# Run
python -m mcp_server_selenium --port 9222 --user_data_dir /tmp/chrome-debug

# Or use script entry point
selenium-mcp-server --port 9222 --user_data_dir /tmp/chrome-debug
```

### Driver Options
```bash
# Use normal ChromeDriver (default)
python -m mcp_server_selenium --driver normal_chromedriver

# Use undetected ChromeDriver (stealth mode)
python -m mcp_server_selenium --driver undetected_chrome_driver

# With custom Chrome profile
python -m mcp_server_selenium --profile "Profile 1"
```

## Testing and Development

### MCP Inspector (Interactive Testing)
```bash
# Using uv (recommended)
uv run mcp dev src/mcp_server_selenium/__main__.py

# Or with make
make inspector

# Access at: http://127.0.0.1:6274/#tools
```

### Direct Tool Testing
```bash
# Interactive Python mode for direct tool testing
.venv/bin/python -i test_call_tools_directly.py

# Then in Python interactive mode:
>>> test_get_style_an_element()
>>> test_undetected_chrome()
```

### Log Monitoring
```bash
# Watch log file in real-time
tailf /tmp/selenium-mcp.log
```

## Project Management

### Virtual Environment
```bash
# Activate virtual environment (if using venv)
source .venv/bin/activate

# Deactivate
deactivate
```

### Package Building (for distribution)
```bash
# Build package
python -m build

# Or with uv
uv build
```

## System Commands (Linux)

### File Operations
- `ls -la`: List files with details
- `cd <path>`: Change directory
- `cat <file>`: Display file contents
- `grep <pattern> <file>`: Search for pattern in file
- `find <path> -name <pattern>`: Find files by name

### Process Management
- `ps aux | grep chrome`: Find Chrome processes
- `kill <pid>`: Kill process by ID
- `pkill chrome`: Kill all Chrome processes

### Git Operations
- `git status`: Check repository status
- `git log --oneline`: View commit history
- `git diff`: View changes
- `git add .`: Stage all changes
- `git commit -m "message"`: Commit changes
