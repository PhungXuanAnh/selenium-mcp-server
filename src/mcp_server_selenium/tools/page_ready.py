import logging
import time
from ..server import mcp, ensure_driver_initialized

logger = logging.getLogger(__name__)


@mcp.tool()
def check_page_ready(wait_seconds: int = 0) -> str:
    """Check if the current page is fully loaded.
    
    This tool checks the document.readyState of the current page to determine if it has
    finished loading. It can optionally wait a specified number of seconds before checking.
    
    Args:
        wait_seconds: Number of seconds to wait before checking the page's ready state.
            Default is 0 (check immediately).
    
    Returns:
        A message indicating the current ready state of the page (complete, interactive, or loading).
    """
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        raise RuntimeError(str(e))
    
    # Wait the specified number of seconds if requested
    if wait_seconds > 0:
        logger.info(f"Waiting {wait_seconds} seconds before checking page ready state")
        time.sleep(wait_seconds)
    
    try:
        # Get the current document.readyState
        ready_state = driver.execute_script('return document.readyState')
        current_url = driver.current_url
        
        logger.info(f"Current document.readyState: {ready_state}, URL: {current_url}")
        
        # Return a formatted response with details
        if ready_state == 'complete':
            return f"Page is fully loaded (readyState: {ready_state}) at URL: {current_url}"
        elif ready_state == 'interactive':
            return f"Page is partially loaded (readyState: {ready_state}) at URL: {current_url}"
        else:
            return f"Page is still loading (readyState: {ready_state}) at URL: {current_url}"
    
    except Exception as e:
        logger.error(f"Error checking page ready state: {str(e)}")
        raise Exception(f"Error checking page ready state: {str(e)}")