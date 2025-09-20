import logging
from typing import Optional, Union

from mcp.server.fastmcp import FastMCP
from .drivers.normal_chrome import NormalChromeDriver
from .drivers.undetected_chrome import UndetectedChromeDriver

logger = logging.getLogger(__name__)

# Global variable to store WebDriver instance
driver_instance: Optional[Union[NormalChromeDriver, UndetectedChromeDriver]] = None

# Global variable for Chrome user data directory
user_data_dir: str = ""

# Global variable for Chrome debugging port
debug_port: int = 9222

# Global variable for driver type
driver_type: str = "normal_chromedriver"

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


def initialize_driver_instance(custom_user_data_dir: str = "", custom_debug_port: Optional[int] = None):
    """Initialize the global driver instance based on driver type."""
    global driver_instance, user_data_dir, debug_port, driver_type
    
    # Use custom values if provided
    data_dir = custom_user_data_dir or user_data_dir
    port = custom_debug_port or debug_port
    
    # Get the appropriate driver class
    driver_class = get_driver_factory(driver_type)
    
    # Initialize the driver instance
    driver_instance = driver_class(user_data_dir=data_dir, debug_port=port)
    
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
