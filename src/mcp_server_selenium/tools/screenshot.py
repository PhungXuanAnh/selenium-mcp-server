from typing import Optional
import logging
from datetime import datetime
from pathlib import Path
from ..server import mcp, ensure_driver_initialized, auto_recover_stale_window

logger = logging.getLogger(__name__)


@mcp.tool()
@auto_recover_stale_window
def take_screenshot(save_path: Optional[str] = None) -> str:
    """Take a screenshot of the current browser window.
    
    This tool captures the current visible area of the browser window and saves it
    as a PNG file. By default, it saves to the current project directory.
    
    Args:
        save_path: Optional exact file path where the screenshot should be saved. Parent
            directories are created automatically. If omitted, a timestamped PNG file is
            created in the current project directory.
    
    Returns:
        The path to the saved screenshot file.
    """
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        raise RuntimeError(str(e))
    
    if save_path:
        screenshot_path = Path(save_path).expanduser()
        if screenshot_path.exists() and screenshot_path.is_dir():
            raise ValueError("save_path must be a file path, not a directory")
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = Path.cwd() / f"screenshot_{timestamp}.png"

    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    driver.save_screenshot(str(screenshot_path))
    
    return f"Screenshot saved to {screenshot_path}"
