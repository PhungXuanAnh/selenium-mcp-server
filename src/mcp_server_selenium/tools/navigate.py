import logging
import time
from venv import logger
from selenium.common.exceptions import TimeoutException
from ..server import mcp, ensure_driver_initialized

logger = logging.getLogger(__name__)


@mcp.tool()
def navigate(url: str, timeout: int = 60) -> str:
    """Navigate to a specified URL with the Chrome browser.
    
    This tool navigates the browser to the provided URL. If the URL doesn't start with 
    http:// or https://, https:// will be added automatically.
    
    Args:
        url: The URL to navigate to. Will add https:// if protocol is missing.
        timeout: Maximum time in seconds to wait for the navigation to complete.
            Default is 60 seconds. If page load takes longer, a network abort/cancel may occur.
    
    Returns:
        A message confirming navigation started or reporting any issues.
    """
    global driver
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        raise RuntimeError(str(e))
    
    logger.info(f"Starting navigation to {url} with timeout {timeout} seconds")
    
    # Ensure URL has a proper protocol (http:// or https://)
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        logger.info(f"Added https:// protocol, URL is now {url}")
    
    navigation_timeout = timeout
    driver.set_page_load_timeout(navigation_timeout)
    logger.info(f"Set page load timeout to {navigation_timeout} seconds")
    
    start_time = time.time()
    try:
        # remove performance log file if exists before navigation
        import os
        if os.path.exists('/tmp/performance_logs.json'):
            os.remove('/tmp/performance_logs.json')

        # Start navigation
        logger.info(f"Calling driver.get({url})")
        driver.get(url)
        elapsed = time.time() - start_time
        logger.info(f"driver.get() completed in {elapsed:.2f} seconds")
        
        # Return immediately after navigation starts
        return f"Navigation to {url} initiated"
        
    except TimeoutException:
        # This catches the initial navigation timeout
        elapsed = time.time() - start_time
        current_url = driver.current_url
        logger.info(f"Navigation timed out after {elapsed:.2f} seconds. Current URL: {current_url}")
        
        if current_url and current_url != "about:blank" and current_url != "data:,":
            return f"Navigation to {url} started but timed out after {navigation_timeout} seconds. You can use check_page_ready tool to check if the page is loaded. Current URL: {current_url}"
        else:
            return f"Navigation to {url} timed out after {navigation_timeout} seconds, but may continue loading. You can use check_page_ready tool to check if the page is loaded. Current URL: {current_url}"
    except Exception as e:
        elapsed = time.time() - start_time
        error_msg = str(e)
        logger.error(f"Error after {elapsed:.2f} seconds while navigating to {url}: {error_msg}")
        
        # Check if the error is due to the browser being closed
        if "invalid session id" in error_msg and "browser has closed" in error_msg:
            logger.info("Detected that Chrome has been closed. Attempting to restart Chrome...")
            
            # Import server module to access driver instance and restart functionality
            from .. import server
            
            # Reset the driver instance to force reinitialization
            server.driver_instance = None
            
            # Attempt to reinitialize the driver
            try:
                driver = ensure_driver_initialized()
                logger.info("WebDriver reinitialized successfully")
                
                # Try to navigate again
                try:
                    driver.set_page_load_timeout(navigation_timeout)
                    driver.get(url)
                    return f"Chrome was restarted and navigation to {url} initiated"
                except Exception as nav_e:
                    return f"Chrome was restarted but navigation failed: {str(nav_e)}"
            except Exception as init_e:
                return f"Failed to reinitialize WebDriver: {str(init_e)}"
        
        # For other errors, just raise the exception
        raise Exception(f"Error navigating to {url}: {error_msg}")
