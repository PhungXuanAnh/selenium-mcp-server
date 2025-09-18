from typing import Optional
import logging
from datetime import datetime
from pathlib import Path
from mcp_server_selenium.server import mcp, ensure_driver_initialized

logger = logging.getLogger(__name__)


@mcp.tool()
def take_screenshot(save_path: Optional[str] = None) -> str:
    """Take a screenshot of the current browser window.
    
    This tool captures the current visible area of the browser window and saves it
    as a PNG file. By default, it saves to the current project directory.
    
    Args:
        save_path: Optional path where the screenshot should be saved. If not provided,
                  it will save to the current project directory.
    
    Returns:
        The path to the saved screenshot file.
    """
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        raise RuntimeError(str(e))
    
    # Determine where to save the screenshot
    if save_path:
        screenshot_dir = Path(save_path)
    else:
        # Use current working directory (project root)
        screenshot_dir = Path.cwd()
    
    # Create the directory if it doesn't exist
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate a filename automatically
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"screenshot_{timestamp}.png"
    
    screenshot_path = screenshot_dir / filename
    driver.save_screenshot(str(screenshot_path))
    
    return f"Screenshot saved to {screenshot_path}"