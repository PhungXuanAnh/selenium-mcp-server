import logging
from datetime import datetime
from pathlib import Path
from mcp_server_selenium.server import mcp, ensure_driver_initialized

logger = logging.getLogger(__name__)


@mcp.tool()
def take_screenshot() -> str:
    """Take a screenshot of the current browser window.
    
    This tool captures the current visible area of the browser window and saves it
    as a PNG file in the ~/selenium-mcp/screenshot directory. The filename will include
    a timestamp for uniqueness.
    
    Returns:
        The path to the saved screenshot file.
    """
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        raise RuntimeError(str(e))
    
    # Create the screenshot directory if it doesn't exist
    screenshot_dir = Path.home() / "selenium-mcp" / "screenshot"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate a filename automatically
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"screenshot_{timestamp}.png"
    
    screenshot_path = screenshot_dir / filename
    driver.save_screenshot(str(screenshot_path))
    
    return f"Screenshot saved to {screenshot_path}"