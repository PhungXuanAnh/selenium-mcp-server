import functools
import logging
import socket
from pathlib import Path
from typing import Optional, Union

from mcp.server.fastmcp import FastMCP
from .drivers.normal_chrome import NormalChromeDriver
from .drivers.undetected_chrome import UndetectedChromeDriver

logger = logging.getLogger(__name__)

# Global variable to store WebDriver instance
driver_instance: Optional[Union[NormalChromeDriver, UndetectedChromeDriver]] = None

# Global variable for Chrome user data directory
user_data_dir: str = ""

# Global variable for Chrome debugging port (0 = auto-detect)
debug_port: int = 0

# Base directory used to resolve relative browser artifact paths.
workspace_root: Path = Path.cwd().resolve()

# Controlled Chrome download destination. ``None`` means workspace default.
download_directory: Optional[Path] = None
_configured_download_session: str = ""


def get_workspace_root() -> Path:
    """Return the configured workspace root as an absolute resolved path."""
    return workspace_root.resolve()


def get_download_directory() -> Path:
    """Return the configured absolute Chrome download destination."""
    if download_directory is None:
        return (get_workspace_root() / "tmp/selenium-downloads").resolve()
    requested = Path(download_directory).expanduser()
    if requested.is_absolute():
        return requested.resolve()
    if ".." in requested.parts:
        raise ValueError("relative download directory cannot contain path traversal")
    return (get_workspace_root() / requested).resolve()


def configure_download_directory(driver) -> Path:
    """Apply one download directory to an attached or newly started Chrome session."""
    global _configured_download_session
    destination = get_download_directory()
    destination.mkdir(parents=True, exist_ok=True)
    session = str(getattr(driver, "session_id", id(driver)))
    if session == _configured_download_session:
        return destination
    try:
        driver.execute_cdp_cmd(
            "Browser.setDownloadBehavior",
            {
                "behavior": "allow",
                "downloadPath": str(destination),
                "eventsEnabled": True,
            },
        )
    except Exception:
        driver.execute_cdp_cmd(
            "Page.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(destination)},
        )
    _configured_download_session = session
    return destination


def find_available_port(start: int = 20000, end: int = 30000) -> int:
    """Find an available port in the given range."""
    for port in range(start, end):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.1)
                result = s.connect_ex(('127.0.0.1', port))
                if result != 0:  # Port is NOT in use
                    return port
        except OSError:
            continue
    raise RuntimeError(f"No available port found in range {start}-{end}")

# Global variable for driver type
driver_type: str = "normal_chromedriver"

# Global variable for Chrome profile
profile: str = "Default"

MCP_INSTRUCTIONS = """
One Selenium session has exactly one active tab context. Browser tools use it. Call
list_tabs then switch_tab(handle) to change context; open_tab activates its new tab and
close_tab reports the successor. Tab-sensitive calls must be serialized; use separate
sessions for parallel work. For take_screenshot choose a semantic file_name. Prefer an
absolute directory inside your current workspace when known; otherwise omit directory.
""".strip()

COMPACT_MCP_INSTRUCTIONS = """
One browser session and its active tab are shared mutable state; serialize tab-sensitive
calls. Recommended workflow: tabs(list) -> navigate -> wait_for -> query_elements ->
interact_element -> take_screenshot. Element refs are document-scoped; query again after
navigation. browser_logs owns bounded session-local buffers: peek preserves entries,
consume removes returned entries, and redaction is on by default. tabs(list) reports
browser versions, current page state, and the controlled download directory. Downloads
default under the workspace. Screenshots, uploads, response bodies, raw logs, tabs, and
localStorage can expose sensitive or cross-origin data; use explicit paths/raw opt-ins
only when authorized.
""".strip()

# Initialize FastMCP
mcp = FastMCP(
    name="mcp-selenium-sync",
    instructions=MCP_INSTRUCTIONS,
)

compact_mcp = FastMCP(
    name="mcp-selenium-sync-compact",
    instructions=COMPACT_MCP_INSTRUCTIONS,
)


def get_driver_factory(driver_type: str = "normal_chromedriver"):
    """Get the appropriate driver factory based on driver type."""
    if driver_type == "normal_chromedriver":
        return NormalChromeDriver
    elif driver_type == "undetected_chrome_driver":
        # Check if undetected chrome driver is available
        from .drivers.undetected_chrome import UC_AVAILABLE
        if not UC_AVAILABLE:
            raise ImportError(
                "undetected-chromedriver is not installed. "
                "Please install it with: pip install undetected-chromedriver"
            )
        return UndetectedChromeDriver
    else:
        raise ValueError(f"Unsupported driver type: {driver_type}")


def initialize_driver_instance(custom_user_data_dir: str = "", custom_debug_port: Optional[int] = None, custom_profile: str = ""):
    """Initialize the global driver instance based on driver type."""
    global driver_instance, user_data_dir, debug_port, driver_type, profile
    global _configured_download_session
    
    # Use custom values if provided
    data_dir = custom_user_data_dir or user_data_dir
    port = custom_debug_port or debug_port
    profile_name = custom_profile or profile
    
    # Get the appropriate driver class
    driver_class = get_driver_factory(driver_type)
    
    # Initialize the driver instance
    driver_instance = driver_class(user_data_dir=data_dir, profile=profile_name)
    _configured_download_session = ""
    
    logger.info(f"Initialized {driver_type} driver instance")
    return driver_instance


def ensure_driver_initialized():
    """Ensure that the WebDriver is initialized.
    
    This function checks if the global WebDriver instance is initialized.
    If not, it initializes a new WebDriver instance.
    
    Returns:
        The initialized WebDriver instance.
        
    Raises:
        RuntimeError: If the WebDriver fails to initialize.
    """
    global driver_instance
    
    if driver_instance is None:
        logger.info("Driver instance is not initialized, initializing now...")
        driver_instance = initialize_driver_instance()
    
    # Ensure the actual selenium driver is initialized
    driver = driver_instance.ensure_driver_initialized()
    configure_download_directory(driver)
    return driver


def recover_from_stale_window() -> None:
    """Recover from a 'no such window' error by switching to a valid window.

    Call this from any tool's except block when the error message contains
    'no such window' or 'target window already closed'.  It is logged to
    the file as a WARNING but the error is NOT returned to the MCP client —
    the tool should retry its operation after calling this.
    """
    global driver_instance
    if driver_instance is not None:
        logger.warning("Stale window detected — recovering silently")
        driver_instance._recover_window_handle()


def is_stale_window_error(error_msg: str) -> bool:
    """Check if an error message indicates a stale/closed window."""
    return "no such window" in error_msg or "target window already closed" in error_msg


def auto_recover_stale_window(func):
    """Decorator: silently recover from 'no such window' errors and retry once.

    If the wrapped function raises an exception whose message indicates a stale
    window, the decorator will:
      1. Log the error to the log file (WARNING, not ERROR)
      2. Call recover_from_stale_window() to switch to a valid tab
      3. Re-call ensure_driver_initialized() to refresh the driver reference
      4. Retry the function exactly once
    If the retry also fails, the exception propagates normally.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if is_stale_window_error(str(e)):
                logger.warning(
                    f"Stale window in {func.__name__}() — recovering and retrying"
                )
                recover_from_stale_window()
                return func(*args, **kwargs)
            raise
    return wrapper


def get_driver():
    """Get the current selenium driver instance."""
    global driver_instance
    
    if driver_instance is None:
        ensure_driver_initialized()
    
    if driver_instance is not None:
        return driver_instance.driver
    else:
        raise RuntimeError("Driver instance is not initialized")


def quit_driver():
    """Quit the current driver instance."""
    global driver_instance, _configured_download_session
    
    if driver_instance is not None:
        driver_instance.quit()
        driver_instance = None
        _configured_download_session = ""
