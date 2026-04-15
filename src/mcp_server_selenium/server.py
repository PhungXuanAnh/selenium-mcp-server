import functools
import logging
import socket
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

# Initialize FastMCP
mcp = FastMCP(
    name="mcp-selenium-sync",
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
    
    # Use custom values if provided
    data_dir = custom_user_data_dir or user_data_dir
    port = custom_debug_port or debug_port
    profile_name = custom_profile or profile
    
    # Get the appropriate driver class
    driver_class = get_driver_factory(driver_type)
    
    # Initialize the driver instance
    driver_instance = driver_class(user_data_dir=data_dir, profile=profile_name)
    
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
    return driver_instance.ensure_driver_initialized()


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
    global driver_instance
    
    if driver_instance is not None:
        driver_instance.quit()
        driver_instance = None
