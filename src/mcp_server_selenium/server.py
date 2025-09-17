import json
import logging
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

# Global variable to store WebDriver instance
driver: Optional[webdriver.Chrome] = None

# Global variable for Chrome user data directory
user_data_dir: str = ""

# Global variable for Chrome debugging port
debug_port: int = 9222

# Initialize FastMCP
mcp = FastMCP(
    name="mcp-selenium-sync",
)


def check_chrome_debugger_port() -> bool:
    """Check if Chrome is running with remote debugging port open"""
    global debug_port
    try:
        # Try to connect to the port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('127.0.0.1', debug_port))
            return result == 0
    except Exception as e:
        logger.error(f"Error checking Chrome debugger port: {str(e)}")
        return False

def start_chrome(custom_user_data_dir: str = "") -> bool:
    """Start Chrome with remote debugging enabled on specified port"""
    global user_data_dir
    global debug_port
    try:
        if custom_user_data_dir:
            user_data_dir = custom_user_data_dir
        elif not user_data_dir:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            user_data_dir = f"/tmp/chrome-debug-{timestamp}"
        
        logger.info(f"Starting Chrome with debugging port {debug_port} and user data dir {user_data_dir}")
        
        # Start Chrome as a subprocess
        cmd = [
            "google-chrome-stable",
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--start-maximized",  # Start Chrome maximized
            "--auto-open-devtools-for-tabs"  # Auto-open DevTools for new tabs
        ]
        
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            start_new_session=True  # Detach from the parent process
        )
        
        # Wait a moment for Chrome to start
        time.sleep(3)
        
        # Check if Chrome started correctly
        if check_chrome_debugger_port():
            logger.info(f"Chrome started successfully on port {debug_port}")
            return True
        else:
            logger.error("Failed to start Chrome or confirm debugging port is open")
            return False
    except Exception as e:
        logger.error(f"Error starting Chrome: {str(e)}")
        return False

def initialize_driver(custom_user_data_dir: str = "") -> webdriver.Chrome:
    """Initialize and return a WebDriver instance based on browser choice"""
    global driver
    global user_data_dir
    global debug_port
    
    # Set user_data_dir if provided
    if custom_user_data_dir:
        user_data_dir = custom_user_data_dir
    
    # Check if Chrome is already running with remote debugging
    if not check_chrome_debugger_port():
        logger.info(f"Chrome not detected on port {debug_port}, attempting to start a new instance")
        
        # Start Chrome with DevTools auto-open
        if not user_data_dir:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            user_data_dir = f"/tmp/chrome-debug-{timestamp}"
        
        logger.info(f"Starting Chrome with debugging port {debug_port} and user data dir {user_data_dir}")
        
        # Start Chrome as a subprocess with DevTools auto-open
        cmd = [
            "google-chrome-stable",
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--enable-logging",  # Enable logging
            "--start-maximized",  # Start Chrome maximized
            "--auto-open-devtools-for-tabs"  # Auto-open DevTools for new tabs
        ]
        
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            start_new_session=True  # Detach from the parent process
        )
        
        # Wait a moment for Chrome to start
        time.sleep(3)
        
        if not check_chrome_debugger_port():
            raise RuntimeError("Failed to start Chrome browser")
    else:
        logger.info(f"Chrome already running with remote debugging port {debug_port}")
    
    # Setup capabilities to enable browser logging
    options = ChromeOptions()
    options.debugger_address = f"127.0.0.1:{debug_port}"
    
    # Set logging preferences for both browser logs and performance logs
    options.set_capability('goog:loggingPrefs', {
        'browser': 'ALL',
        'performance': 'ALL'
    })
    
    # Create the driver
    driver = webdriver.Chrome(options=options)
    
    # Maximize the window
    driver.maximize_window()
    
    # Set longer page load timeout
    driver.set_page_load_timeout(120)
    driver.set_script_timeout(120)
    
    return driver

def open_devtools_and_wait(panel: str) -> None:
    """Open Chrome DevTools and switch to specified panel"""
    global driver
    if driver is None:
        raise RuntimeError("WebDriver is not initialized")
    
    logger.info(f"Opening DevTools with panel: {panel}")
    
    # Open DevTools
    driver.execute_script("window.open('chrome-devtools://devtools/bundled/devtools_app.html', 'devtools');")
    
    # Switch to DevTools tab
    original_window = driver.current_window_handle
    for window_handle in driver.window_handles:
        if window_handle != original_window:
            driver.switch_to.window(window_handle)
            break
    
    # Wait for DevTools to load
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".toolbar"))
        )
        
        # Switch to the specified panel
        if panel == "console":
            panel_script = """
            const panelButton = document.querySelector('.toolbar-button[aria-label="Console"]');
            if (panelButton) panelButton.click();
            """
        elif panel == "network":
            panel_script = """
            const panelButton = document.querySelector('.toolbar-button[aria-label="Network"]');
            if (panelButton) panelButton.click();
            """
        else:
            raise ValueError(f"Unsupported DevTools panel: {panel}")
        
        driver.execute_script(panel_script)
        time.sleep(1)  # Give the panel time to activate
        
    except Exception as e:
        logger.error(f"Error opening DevTools panel {panel}: {str(e)}")
        # Close DevTools tab and switch back to original
        driver.close()
        driver.switch_to.window(original_window)
        raise
    
    # Return to original window
    driver.switch_to.window(original_window)

def get_browser_logs(driver: webdriver.Chrome, log_type='browser'):
    """Get logs from the browser and format them"""
    logs = []
    try:
        browser_logs = driver.get_log(log_type)
        for entry in browser_logs:
            logs.append({
                'type': entry.get('level', 'INFO').lower(),
                'message': entry.get('message', ''),
                'timestamp': entry.get('timestamp', 0)
            })
    except Exception as e:
        logger.error(f"Error getting browser logs: {str(e)}")
    
    return logs

def process_performance_log_entry(entry):
    """Process a performance log entry to extract the message"""
    try:
        return json.loads(entry['message'])['message']
    except Exception as e:
        logger.error(f"Error processing performance log entry: {str(e)}")
        return None

def get_network_logs_from_performance(driver: webdriver.Chrome, filter_url_by_text: str = ''):
    """Get network logs using performance logging"""
    if driver is None:
        return []
    
    try:
        # Get raw performance logs
        performance_logs = driver.get_log('performance')
        
        # Process the logs to extract the message part
        events = []
        for entry in performance_logs:
            event = process_performance_log_entry(entry)
            if event is not None:
                events.append(event)
        
        # Filter for network events
        network_events = []
        for event in events:
            if 'Network.' in event.get('method', ''):
                # Extract the relevant information
                method = event.get('method', '')
                params = event.get('params', {})
                request_id = params.get('requestId', '')
                
                # Create a simplified event object
                if method == 'Network.requestWillBeSent':
                    request = params.get('request', {})
                    network_events.append({
                        'type': 'request',
                        'requestId': request_id,
                        'method': request.get('method', ''),
                        'url': request.get('url', ''),
                        'timestamp': params.get('timestamp', 0),
                        'headers': request.get('headers', {})
                    })
                elif method == 'Network.responseReceived':
                    response = params.get('response', {})
                    status = response.get('status', 0)
                    status_text = response.get('statusText', '')
                    
                    network_events.append({
                        'type': 'response',
                        'requestId': request_id,
                        'status': status,
                        'statusText': status_text,
                        'url': response.get('url', ''),
                        'timestamp': params.get('timestamp', 0),
                        'headers': response.get('headers', {}),
                        'mimeType': response.get('mimeType', ''),
                        'hasError': status >= 400
                    })
                elif method == 'Network.loadingFailed':
                    error_text = params.get('errorText', '')
                    canceled = params.get('canceled', False)
                    
                    network_events.append({
                        'type': 'failed',
                        'requestId': request_id,
                        'errorText': error_text,
                        'canceled': canceled,
                        'timestamp': params.get('timestamp', 0),
                        'hasError': True
                    })
        
        # Group network events by requestId
        grouped_events: Dict[str, List[Dict[str, Any]]] = {}
        for event in network_events:
            request_id = event.get('requestId', '')
            if request_id not in grouped_events:
                grouped_events[request_id] = []
            grouped_events[request_id].append(event)
        
        # Filter by URL domain text if specified
        if filter_url_by_text:
            logger.info(f"Filtering network logs by domain containing: {filter_url_by_text}")
            filtered_events = {}
            for request_id, events_list in grouped_events.items():
                # Check if any event in this group has a URL domain containing the filter text
                for event in events_list:
                    if 'url' in event:
                        try:
                            domain = urlparse(event['url']).netloc
                            if filter_url_by_text in domain:
                                filtered_events[request_id] = events_list
                                break
                        except Exception as e:
                            logger.error(f"Error parsing URL domain: {str(e)}")
            grouped_events = filtered_events
        
        # Convert dictionary to list of lists
        result = list(grouped_events.values())
        
        return result
    except Exception as e:
        logger.error(f"Error getting network logs from performance: {str(e)}")
        return []

def ensure_driver_initialized() -> webdriver.Chrome:
    """Ensure that the WebDriver is initialized.
    
    This function checks if the global WebDriver instance is initialized.
    If not, it initializes a new WebDriver instance.
    
    Returns:
        The initialized WebDriver instance.
        
    Raises:
        RuntimeError: If the WebDriver fails to initialize.
    """
    global driver
    global user_data_dir
    
    if driver is None:
        logger.info("WebDriver is not initialized, initializing now...")
        try:
            driver = initialize_driver(custom_user_data_dir=user_data_dir)
            logger.info("WebDriver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {str(e)}")
            raise RuntimeError(f"Failed to initialize WebDriver: {str(e)}")
    return driver

@mcp.tool()
def navigate(url: str, timeout: int = 60) -> str:
    """Navigate to a specified URL with the Chrome browser.
    
    This tool navigates the browser to the provided URL. If the URL doesn't start with 
    http:// or https://, https:// will be added automatically.
    
    Args:
        url: The URL to navigate to. Will add https:// if protocol is missing.
        timeout: Maximum time in seconds to wait for the navigation to complete.
            Default is 60 seconds.
    
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
    
    # Use a shorter timeout for navigation to avoid MCP timeout
    navigation_timeout = min(timeout, 5)  # Limit to 5 seconds for initial navigation
    driver.set_page_load_timeout(navigation_timeout)
    logger.info(f"Set page load timeout to {navigation_timeout} seconds")
    
    start_time = time.time()
    try:
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
            
            # Attempt to restart Chrome
            if start_chrome():
                logger.info("Successfully restarted Chrome")
                
                # Reinitialize the driver
                try:
                    driver = initialize_driver()
                    logger.info("WebDriver reinitialized successfully")
                    
                    # Try to navigate again
                    try:
                        driver.set_page_load_timeout(navigation_timeout)
                        driver.get(url)
                        return f"Chrome was restarted and navigation to {url} initiated"
                    except Exception as nav_e:
                        return f"Chrome was restarted but navigation failed: {str(nav_e)}"
                except Exception as init_e:
                    return f"Chrome was restarted but failed to reinitialize WebDriver: {str(init_e)}"
            else:
                return f"Failed to restart Chrome after it was closed"
        
        # For other errors, just raise the exception
        raise Exception(f"Error navigating to {url}: {error_msg}")

@mcp.tool()
def take_screenshot() -> str:
    """Take a screenshot of the current browser window.
    
    This tool captures the current visible area of the browser window and saves it
    as a PNG file in the ~/selenium-mcp/screenshot directory. The filename will include
    a timestamp for uniqueness.
    
    Returns:
        The path to the saved screenshot file.
    """
    global driver
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
    global driver
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

@mcp.tool()
def get_console_logs(log_level: str = "") -> str:
    """Retrieve console logs from the browser with optional filtering by log level.
    
    This tool collects console logs that have been output in the browser's JavaScript console 
    since the page was loaded. Results can be filtered by log level.
    
    Args:
        log_level: The log level to filter by (e.g., "INFO", "WARNING", "ERROR", "SEVERE").
            When empty, returns all log levels.
    
    Returns:
        A JSON string containing console log entries, including their type and message.
    """
    global driver
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        return f"Failed to initialize WebDriver: {str(e)}"
    
    try:
        # Get browser logs
        logs = get_browser_logs(driver)
        
        # Filter logs by level if specified
        if log_level:
            log_level = log_level.lower()
            logs = [log for log in logs if log['type'].lower() == log_level]
        
        return json.dumps(logs, indent=2)
    except Exception as e:
        logger.error(f"Error getting console logs: {str(e)}")
        return f"Error getting console logs: {str(e)}"

@mcp.tool()
def get_network_logs(filter_url_by_text: str = '', only_errors_log: bool = False) -> str:
    """Retrieve network request logs from the browser.
    
    This tool collects all network activity (requests and responses) that has occurred
    since the page was loaded. Results can optionally be filtered by domain.
    
    Args:
        filter_url_by_text: Text to filter domain names by. When specified, only network
            requests to domains containing this text will be included. Default is empty
            string (no filtering). You should filter by domain because the network logs are too many.
        only_errors_log: When True, only returns network requests with error status codes (4xx/5xx)
            or other network failures. Default is False (returns all network logs).
    
    Returns:
        A JSON string containing the network request logs, grouped by request ID.
    """
    global driver
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        return f"Failed to initialize WebDriver: {str(e)}"
    
    try:
        # Get network logs from performance data
        network_logs = get_network_logs_from_performance(driver, filter_url_by_text)
        
        # Filter for errors only if only_errors_log is True
        if only_errors_log:
            # Filter for errors only (status >= 400 or failed requests)
            error_logs = []
            for request_events in network_logs:
                # Check if any event in this request group has an error
                has_error = any(event.get('hasError', False) for event in request_events)
                if has_error:
                    error_logs.append(request_events)
            
            network_logs = error_logs
        
        # Return formatted logs
        return json.dumps(network_logs, indent=2)
    except Exception as e:
        logger.error(f"Error getting network logs: {str(e)}")
        return f"Error getting network logs: {str(e)}"

@mcp.tool()
def get_an_element(text: str = '', class_name: str = '', id: str = '', attributes: dict = {}, element_type: str = '', in_iframe_id: str = '', in_iframe_name: str = '', return_html: bool = False, xpath: str = '') -> str:
    """Get an element identified by text content, class name, or ID.
    
    This tool finds an element based on specified criteria. At least one 
    of text, class_name, id, attributes, element_type, or xpath must be provided. If multiple elements match the criteria, 
    or if no elements are found, an error message is returned.
    
    Args:
        text: Text content of the element to find. Case-sensitive text matching.
        class_name: CSS class name of the element to find.
        id: ID attribute of the element to find.
        attributes: Dictionary of attribute name-value pairs to match (e.g. {'data-test': 'button'}).
        element_type: HTML element type to find (e.g. 'div', 'input', 'h1', 'button', etc.).
        in_iframe_id: ID of the iframe to search within. If provided, the function will switch to this iframe before searching.
        in_iframe_name: Name of the iframe to search within. If provided and in_iframe_id is not provided, the function will switch to this iframe before searching.
        return_html: Return the HTML content of the element instead of JSON information.
        xpath: Direct XPath selector to find the element. When provided, other selection criteria are ignored.
    
    Returns:
        A JSON string with information about the found element or an error message.
        If return_html is True, returns the HTML content of the element.
    """
    global driver
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        return f"Failed to initialize WebDriver: {str(e)}"
    
    if text == '' and class_name == '' and id == '' and not attributes and element_type == '' and xpath == '':
        return "Error: At least one of text, class_name, id, attributes, element_type, or xpath must be provided"
    
    try:
        # Remember the original context to switch back later
        original_context = True
        
        # Switch to iframe if specified
        if in_iframe_id or in_iframe_name:
            logger.info(f"Switching to iframe with id='{in_iframe_id}' or name='{in_iframe_name}'")
            try:
                if in_iframe_id:
                    # First try to find the iframe by ID
                    iframe = driver.find_element(By.ID, in_iframe_id)
                    driver.switch_to.frame(iframe)
                    logger.info(f"Successfully switched to iframe with id='{in_iframe_id}'")
                elif in_iframe_name:
                    # If ID not provided, try by name
                    driver.switch_to.frame(in_iframe_name)
                    logger.info(f"Successfully switched to iframe with name='{in_iframe_name}'")
                original_context = False
            except Exception as iframe_e:
                error_msg = f"Error switching to iframe: {str(iframe_e)}"
                logger.error(error_msg)
                return error_msg
        
        # If xpath is provided, use it directly
        if xpath != '':
            logger.info(f"Looking for elements with provided XPath: {xpath}")
            elements = driver.find_elements(By.XPATH, xpath)
        else:
            # Build XPath conditions based on provided arguments
            conditions = []
            
            if id != '':
                conditions.append(f"@id='{id}'")
            
            if class_name != '':
                # Handle multiple class names by ensuring each is present
                for cn in class_name.split():
                    conditions.append(f"contains(@class, '{cn}')")
            
            if text != '':
                conditions.append(f"contains(text(), '{text}')")
                
            # Add conditions for additional attributes
            for attr_name, attr_value in attributes.items():
                conditions.append(f"@{attr_name}='{attr_value}'")
            
            # Combine conditions with 'and'
            xpath = "//" + (element_type if element_type != '' else "*")
            if conditions:
                xpath += "[" + " and ".join(conditions) + "]"
            
            logger.info(f"Looking for elements with XPath: {xpath}")
            elements = driver.find_elements(By.XPATH, xpath)
        
        # Check if we found exactly one element
        if len(elements) == 0:
            criteria_str = []
            if text != '':
                criteria_str.append(f"text='{text}'")
            if class_name != '':
                criteria_str.append(f"class='{class_name}'")
            if id != '':
                criteria_str.append(f"id='{id}'")
            if element_type != '':
                criteria_str.append(f"element_type='{element_type}'")
            for attr_name, attr_value in attributes.items():
                criteria_str.append(f"{attr_name}='{attr_value}'")
            if xpath != '':
                criteria_str.append(f"xpath='{xpath}'")
            
            error_msg = f"No elements found matching criteria: {', '.join(criteria_str)}"
            logger.error(error_msg)
            
            # Switch back to original context before returning
            if not original_context:
                driver.switch_to.default_content()
                
            return error_msg
        
        if len(elements) > 1:
            error_msg = f"Found {len(elements)} elements matching the criteria. Please provide more specific criteria."
            logger.error(error_msg)
            
            # Switch back to original context before returning
            if not original_context:
                driver.switch_to.default_content()
                
            return error_msg
        
        # Get the element
        element = elements[0]
        
        # If return_html is True, return the HTML content instead of JSON
        if return_html:
            try:
                # Get innerHTML or outerHTML
                inner_html = element.get_attribute("innerHTML")
                outer_html = element.get_attribute("outerHTML")
                
                # Switch back to original context
                if not original_context:
                    driver.switch_to.default_content()
                
                return json.dumps({
                    "innerHTML": inner_html,
                    "outerHTML": outer_html
                })
                
            except Exception as html_e:
                error_msg = f"Error getting HTML content: {str(html_e)}"
                logger.error(error_msg)
                
                # Switch back to original context in case of error
                if not original_context:
                    driver.switch_to.default_content()
                
                return error_msg
        
        # Get element properties for standard JSON response
        try:
            tag_name = element.tag_name
        except:
            tag_name = "unknown"
            
        try:
            element_id = element.get_attribute("id") or "no-id"
        except:
            element_id = "unknown"
            
        try:
            element_class = element.get_attribute("class") or "no-class"
        except:
            element_class = "unknown"
            
        try:
            element_text = element.text[:50] + "..." if len(element.text) > 50 else element.text
        except:
            element_text = "unknown"
            
        # Return element info as JSON
        element_info = {
            "found": True,
            "tag_name": tag_name,
            "id": element_id,
            "class": element_class,
            "text": element_text,
            "xpath": xpath,
            "in_iframe_id": in_iframe_id,
            "in_iframe_name": in_iframe_name
        }
        
        # Switch back to original context
        if not original_context:
            driver.switch_to.default_content()
            
        return json.dumps(element_info)
    
    except Exception as e:
        error_msg = f"Error finding element: {str(e)}"
        logger.error(error_msg)
        
        # Switch back to original context in case of error
        try:
            if 'original_context' in locals() and not original_context:
                driver.switch_to.default_content()
        except:
            pass
            
        return error_msg

@mcp.tool()
def get_elements(text: str = '', class_name: str = '', id: str = '', attributes: dict = {}, element_type: str = '', in_iframe_id: str = '', in_iframe_name: str = '', page: int = 1, page_size: int = 3, return_html: bool = False, xpath: str = '') -> str:
    """Get multiple elements identified by text content, class name, or ID with pagination.
    
    This tool finds elements based on specified criteria. At least one 
    of text, class_name, id, attributes, element_type, or xpath must be provided. Unlike get_an_element,
    this function returns multiple elements with pagination support.
    
    Args:
        text: Text content of the elements to find. Case-sensitive text matching.
        class_name: CSS class name of the elements to find.
        id: ID attribute of the elements to find.
        attributes: Dictionary of attribute name-value pairs to match (e.g. {'data-test': 'button'}).
        element_type: HTML element type to find (e.g. 'div', 'input', 'h1', 'button', etc.).
        in_iframe_id: ID of the iframe to search within. If provided, the function will switch to this iframe before searching.
        in_iframe_name: Name of the iframe to search within. If provided and in_iframe_id is not provided, the function will switch to this iframe before searching.
        page: Current page of elements returned in the response (default: 1).
        page_size: Number of elements to return in the response (default: 3).
        return_html: Return the HTML content of the elements instead of JSON information.
        xpath: Direct XPath selector to find the elements. When provided, other selection criteria are ignored.
    
    Returns:
        A JSON string with information about the found elements or an error message.
        If return_html is True, includes HTML content of the elements.
    """
    global driver
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        return f"Failed to initialize WebDriver: {str(e)}"
    
    if text == '' and class_name == '' and id == '' and not attributes and element_type == '' and xpath == '':
        return "Error: At least one of text, class_name, id, attributes, element_type, or xpath must be provided"
    
    # Validate pagination parameters
    if page < 1:
        return "Error: Page must be at least 1"
    if page_size < 1:
        return "Error: Page size must be at least 1"
    
    try:
        # Remember the original context to switch back later
        original_context = True
        
        # Switch to iframe if specified
        if in_iframe_id or in_iframe_name:
            logger.info(f"Switching to iframe with id='{in_iframe_id}' or name='{in_iframe_name}'")
            try:
                if in_iframe_id:
                    # First try to find the iframe by ID
                    iframe = driver.find_element(By.ID, in_iframe_id)
                    driver.switch_to.frame(iframe)
                    logger.info(f"Successfully switched to iframe with id='{in_iframe_id}'")
                elif in_iframe_name:
                    # If ID not provided, try by name
                    driver.switch_to.frame(in_iframe_name)
                    logger.info(f"Successfully switched to iframe with name='{in_iframe_name}'")
                original_context = False
            except Exception as iframe_e:
                error_msg = f"Error switching to iframe: {str(iframe_e)}"
                logger.error(error_msg)
                return error_msg
        
        # If xpath is provided, use it directly
        if xpath != '':
            logger.info(f"Looking for elements with provided XPath: {xpath}")
            all_elements = driver.find_elements(By.XPATH, xpath)
            search_xpath = xpath
        else:
            # Build XPath conditions based on provided arguments
            conditions = []
            
            if id != '':
                conditions.append(f"@id='{id}'")
            
            if class_name != '':
                # Handle multiple class names by ensuring each is present
                for cn in class_name.split():
                    conditions.append(f"contains(@class, '{cn}')")
            
            if text != '':
                conditions.append(f"contains(text(), '{text}')")
                
            # Add conditions for additional attributes
            for attr_name, attr_value in attributes.items():
                conditions.append(f"@{attr_name}='{attr_value}'")
            
            # Combine conditions with 'and'
            search_xpath = "//" + (element_type if element_type != '' else "*")
            if conditions:
                search_xpath += "[" + " and ".join(conditions) + "]"
            
            logger.info(f"Looking for elements with XPath: {search_xpath}")
            all_elements = driver.find_elements(By.XPATH, search_xpath)
        
        total_elements = len(all_elements)
        total_pages = (total_elements + page_size - 1) // page_size if total_elements > 0 else 1
        
        # Check if we found any elements
        if total_elements == 0:
            criteria_str = []
            if text != '':
                criteria_str.append(f"text='{text}'")
            if class_name != '':
                criteria_str.append(f"class='{class_name}'")
            if id != '':
                criteria_str.append(f"id='{id}'")
            if element_type != '':
                criteria_str.append(f"element_type='{element_type}'")
            for attr_name, attr_value in attributes.items():
                criteria_str.append(f"{attr_name}='{attr_value}'")
            if xpath != '':
                criteria_str.append(f"xpath='{xpath}'")
            
            error_msg = f"No elements found matching criteria: {', '.join(criteria_str)}"
            logger.error(error_msg)
            
            # Switch back to original context before returning
            if not original_context:
                driver.switch_to.default_content()
                
            return json.dumps({
                "found": False,
                "error": error_msg,
                "total_elements": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0,
                "elements": []
            })
        
        # Calculate pagination indices
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total_elements)
        
        # Check if the requested page is valid
        if start_idx >= total_elements:
            error_msg = f"Page {page} exceeds total available pages ({total_pages})"
            logger.error(error_msg)
            
            # Switch back to original context before returning
            if not original_context:
                driver.switch_to.default_content()
                
            return json.dumps({
                "found": True,
                "error": error_msg,
                "total_elements": total_elements,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "elements": []
            })
        
        # Get the paginated elements
        paginated_elements = all_elements[start_idx:end_idx]
        elements_info = []
        
        # Process each element
        for i, element in enumerate(paginated_elements):
            # Generate a unique XPath for this specific element
            try:
                unique_xpath = driver.execute_script("""
                function getPathTo(element) {
                    if (element.id !== '')
                        return '//*[@id="' + element.id + '"]';
                    if (element === document.body)
                        return '/html/body';

                    var ix = 0;
                    var siblings = element.parentNode.childNodes;
                    for (var i = 0; i < siblings.length; i++) {
                        var sibling = siblings[i];
                        if (sibling === element)
                            return getPathTo(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                        if (sibling.nodeType === 1 && sibling.tagName === element.tagName)
                            ix++;
                    }
                }
                return getPathTo(arguments[0]);
                """, element)
            except:
                # Fallback if JS execution fails
                unique_xpath = f"{search_xpath}[{i + 1}]"
                
            if return_html:
                # Get HTML content for this element
                try:
                    inner_html = element.get_attribute("innerHTML")
                    outer_html = element.get_attribute("outerHTML")
                    
                    elements_info.append({
                        "innerHTML": inner_html,
                        "outerHTML": outer_html,
                        "uniqueXPath": unique_xpath
                    })
                except Exception as html_e:
                    elements_info.append({
                        "error": f"Error getting HTML: {str(html_e)}",
                        "innerHTML": "",
                        "outerHTML": "",
                        "uniqueXPath": unique_xpath
                    })
            else:
                # Get standard element info
                try:
                    tag_name = element.tag_name
                except:
                    tag_name = "unknown"
                    
                try:
                    element_id = element.get_attribute("id") or "no-id"
                except:
                    element_id = "unknown"
                    
                try:
                    element_class = element.get_attribute("class") or "no-class"
                except:
                    element_class = "unknown"
                    
                try:
                    element_text = element.text[:50] + "..." if len(element.text) > 50 else element.text
                except:
                    element_text = "unknown"
                
                elements_info.append({
                    "tag_name": tag_name,
                    "id": element_id,
                    "class": element_class,
                    "text": element_text,
                    "uniqueXPath": unique_xpath
                })
        
        # Return elements info as JSON
        result = {
            "found": True,
            "total_elements": total_elements,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "elements": elements_info,
            "xpath": search_xpath,
            "in_iframe_id": in_iframe_id,
            "in_iframe_name": in_iframe_name
        }
        
        # Switch back to original context
        if not original_context:
            driver.switch_to.default_content()
            
        return json.dumps(result)
    
    except Exception as e:
        error_msg = f"Error finding elements: {str(e)}"
        logger.error(error_msg)
        
        # Switch back to original context in case of error
        try:
            if 'original_context' in locals() and not original_context:
                driver.switch_to.default_content()
        except:
            pass
            
        return json.dumps({
            "found": False,
            "error": error_msg,
            "total_elements": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
            "elements": []
        })

@mcp.tool()
def click_to_element(text: str = '', class_name: str = '', id: str = '', attributes: dict = {}, element_type: str = '', in_iframe_id: str = '', in_iframe_name: str = '', element_index: int = -1, xpath: str = '') -> str:
    """Click on an element identified by text content, class name, or ID.
    
    This tool finds and clicks on an element based on specified criteria. At least one 
    of text, class_name, id, attributes, element_type, or xpath must be provided. If multiple elements match the criteria, 
    or if no elements are found, an error message is returned.
    
    Args:
        text: Text content of the element to click. Case-sensitive text matching.
        class_name: CSS class name of the element to click.
        id: ID attribute of the element to click.
        attributes: Dictionary of attribute name-value pairs to match (e.g. {'data-test': 'button'}).
        element_type: HTML element type to find (e.g. 'div', 'input', 'h1', 'button', etc.).
        in_iframe_id: ID of the iframe to search within. If provided, the function will switch to this iframe before searching.
        in_iframe_name: Name of the iframe to search within. If provided and in_iframe_id is not provided, the function will switch to this iframe before searching.
        element_index: Index of the element to click if multiple elements match the criteria. Default is -1 (don't use this parameter).
        xpath: Direct XPath selector to find the element. When provided, other selection criteria are ignored.
    
    Returns:
        A message indicating whether the click was successful or an error message.
    """
    global driver
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        return f"Failed to initialize WebDriver: {str(e)}"
    
    try:
        # Store current URL before the click
        current_url = driver.current_url
        
        if element_index >= 0:
            # Use get_elements to get multiple elements if index is specified
            logger.info(f"Using element_index {element_index} to select from multiple matching elements")
            elements_info = get_elements(text, class_name, id, attributes, element_type, 
                                        in_iframe_id, in_iframe_name, 
                                        page=1, page_size=max(element_index+1, 3),
                                        return_html=False, xpath=xpath)
            
            # Parse the JSON result
            try:
                elements_data = json.loads(elements_info)
                
                # Check if elements were found
                if not isinstance(elements_data, dict) or not elements_data.get("found", False):
                    return elements_info  # Return the error message from get_elements
                
                total_elements = elements_data.get("total_elements", 0)
                
                if total_elements == 0:
                    return f"No elements found matching the given criteria"
                
                if element_index >= total_elements:
                    return f"Index {element_index} is out of bounds. Only {total_elements} elements were found."
                
                # Get all elements matching the criteria using XPath
                elements_xpath = elements_data.get("xpath", "")
                elements_iframe_id = elements_data.get("in_iframe_id", "")
                elements_iframe_name = elements_data.get("in_iframe_name", "")
                
                # Switch to iframe if needed
                original_context = True
                if elements_iframe_id or elements_iframe_name:
                    try:
                        if elements_iframe_id:
                            iframe = driver.find_element(By.ID, elements_iframe_id)
                            driver.switch_to.frame(iframe)
                        elif elements_iframe_name:
                            driver.switch_to.frame(elements_iframe_name)
                        original_context = False
                    except Exception as iframe_e:
                        return f"Error switching to iframe for clicking: {str(iframe_e)}"
                
                # Find all matching elements
                all_elements = driver.find_elements(By.XPATH, elements_xpath)
                
                # Get the element at the specified index
                target_element = all_elements[element_index]
                
                # Get element info for the log message
                element_tag = target_element.tag_name
                element_id = target_element.get_attribute("id") or "no-id"
                element_class = target_element.get_attribute("class") or "no-class"
                element_text = target_element.text[:50] + "..." if len(target_element.text) > 50 else target_element.text
                
                # Click the target element
                target_element.click()
                
                # Wait a moment for any navigation to start
                time.sleep(0.5)
                
                # Switch back to default content
                if not original_context:
                    driver.switch_to.default_content()
                
                # Check if the URL has changed, indicating navigation occurred
                new_url = driver.current_url
                if new_url != current_url:
                    return f"Successfully clicked on element at index {element_index} which triggered navigation from {current_url} to {new_url}"
                
                # If no navigation occurred, return the standard success message
                return f"Successfully clicked on {element_tag} element at index {element_index} with id='{element_id}', class='{element_class}', text='{element_text}'"
                
            except (json.JSONDecodeError, IndexError, Exception) as e:
                return f"Error selecting element at index {element_index}: {str(e)}"
        else:
            # Use the original behavior when element_index is -1
            # Get element using the get_element function
            element_info = get_an_element(text, class_name, id, attributes, element_type, 
                                       in_iframe_id, in_iframe_name, 
                                       return_html=False, xpath=xpath)
            
            # Parse the JSON result
            try:
                element_data = json.loads(element_info)
                
                # Check if the element was found
                if not isinstance(element_data, dict) or not element_data.get("found", False):
                    return element_info  # Return the error message from get_element
                    
                single_tag_name = element_data.get("tag_name", "unknown")
                single_element_id = element_data.get("id", "unknown")
                single_element_class = element_data.get("class", "unknown")
                single_element_text = element_data.get("text", "")
                single_xpath = element_data.get("xpath", "")
                single_iframe_id = element_data.get("in_iframe_id", "")
                single_iframe_name = element_data.get("in_iframe_name", "")
                
                # Switch to iframe if needed
                original_context = True
                if single_iframe_id or single_iframe_name:
                    try:
                        if single_iframe_id:
                            iframe = driver.find_element(By.ID, single_iframe_id)
                            driver.switch_to.frame(iframe)
                        elif single_iframe_name:
                            driver.switch_to.frame(single_iframe_name)
                        original_context = False
                    except Exception as iframe_e:
                        return f"Error switching to iframe for clicking: {str(iframe_e)}"
                
                # Find the element again using the same xpath
                element = driver.find_element(By.XPATH, single_xpath)
                
            except json.JSONDecodeError:
                # get_element returned an error message, not JSON
                return element_info
            
            # Now click the element
            element.click()
            
            # Wait a moment for any navigation to start
            time.sleep(0.5)
            
            # Switch back to default content
            if not original_context:
                driver.switch_to.default_content()
            
            # Check if the URL has changed, indicating navigation occurred
            new_url = driver.current_url
            if new_url != current_url:
                return f"Successfully clicked on {single_tag_name} element which triggered navigation from {current_url} to {new_url}"
            
            # If no navigation occurred, return the standard success message
            return f"Successfully clicked on {single_tag_name} element with id='{single_element_id}', class='{single_element_class}', text='{single_element_text}'"
    
    except Exception as e:
        error_msg = f"Error clicking element: {str(e)}"
        logger.error(error_msg)
        
        # Switch back to default content in case of error
        try:
            if 'original_context' in locals() and not original_context:
                driver.switch_to.default_content()
        except:
            pass
        
        # Check if navigation occurred despite the error
        try:
            new_url = driver.current_url
            if 'current_url' in locals() and new_url != current_url:
                return f"Click succeeded with navigation to {new_url}, but encountered error when reporting: {str(e)}"
        except:
            pass
            
        return error_msg

@mcp.tool()
def set_value_to_input_element(text: str = '', class_name: str = '', id: str = '', attributes: dict = {}, element_type: str = '', input_value: str = '', in_iframe_id: str = '', in_iframe_name: str = '', xpath: str = '') -> str:
    """Set a value to an input element identified by text content, class name, or ID.
    
    This tool finds an input element based on specified criteria and sets the provided value. At least one 
    of text, class_name, id, attributes, element_type, or xpath must be provided. If multiple elements match the criteria, 
    or if no elements are found, an error message is returned.
    
    Args:
        text: Text content of the element to find. Case-sensitive text matching.
        class_name: CSS class name of the element to find.
        id: ID attribute of the element to find.
        attributes: Dictionary of attribute name-value pairs to match (e.g. {'data-test': 'input'}).
        element_type: HTML element type to find (e.g. 'input', 'textarea', 'select', etc.).
        input_value: The value to set on the input element.
        in_iframe_id: ID of the iframe to search within. If provided, the function will switch to this iframe before searching.
        in_iframe_name: Name of the iframe to search within. If provided and in_iframe_id is not provided, the function will switch to this iframe before searching.
        xpath: Direct XPath selector to find the element. When provided, other selection criteria are ignored.
    
    Returns:
        A message indicating whether setting the value was successful or an error message.
    """
    global driver
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        return f"Failed to initialize WebDriver: {str(e)}"
    
    try:
        # Get element using the get_element function
        element_info = get_an_element(text, class_name, id, attributes, element_type, in_iframe_id, in_iframe_name, False, xpath)
        
        # Parse the JSON result
        try:
            element_data = json.loads(element_info)
            
            # Check if the element was found
            if not isinstance(element_data, dict) or not element_data.get("found", False):
                return element_info  # Return the error message from get_element
                
            tag_name = element_data.get("tag_name", "unknown")
            element_id = element_data.get("id", "unknown")
            element_class = element_data.get("class", "unknown")
            xpath = element_data.get("xpath", "")
            iframe_id = element_data.get("in_iframe_id", "")
            iframe_name = element_data.get("in_iframe_name", "")
            
            # Switch to iframe if needed
            original_context = True
            if iframe_id or iframe_name:
                try:
                    if iframe_id:
                        iframe = driver.find_element(By.ID, iframe_id)
                        driver.switch_to.frame(iframe)
                    elif iframe_name:
                        driver.switch_to.frame(iframe_name)
                    original_context = False
                except Exception as iframe_e:
                    return f"Error switching to iframe for setting value: {str(iframe_e)}"
            
            # Find the element again using the same xpath
            element = driver.find_element(By.XPATH, xpath)
            
        except json.JSONDecodeError:
            # get_element returned an error message, not JSON
            return element_info
        
        # Check if element is an input-like element that can accept values
        input_like_tags = ['input', 'textarea', 'select']
        if tag_name and tag_name.lower() not in input_like_tags:
            # Switch back to default content before returning if needed
            if not original_context:
                driver.switch_to.default_content()
            return f"Error: Found element with tag '{tag_name}' is not an input-like element that can accept values"
        
        # Clear existing value
        element.clear()
        
        # Set the new value
        element.send_keys(input_value)
        
        # Verify the value was set (for most input types)
        current_value = element.get_attribute('value')
        
        # Switch back to default content
        if not original_context:
            driver.switch_to.default_content()
        
        return f"Successfully set value '{input_value}' to {tag_name} element with id='{element_id}', class='{element_class}'. Current value: '{current_value}'"
    
    except Exception as e:
        error_msg = f"Error setting value to element: {str(e)}"
        logger.error(error_msg)
        
        # Switch back to default content in case of error
        try:
            if 'original_context' in locals() and not original_context:
                driver.switch_to.default_content()
        except:
            pass
            
        return error_msg

@mcp.tool()
def local_storage_add(key: str, string_value: str = '', object_value: dict = {}, create_empty_string: bool = False, create_empty_object: bool = False) -> str:
    """Add or update a key-value pair in browser's local storage.
    
    This tool adds a new key-value pair to the browser's localStorage, or updates
    the value if the key already exists.
    
    Args:
        key: The key name for the local storage item.
        string_value: The string value to store in local storage. Default is empty string.
        object_value: The object value to store in local storage as JSON. Default is empty dict.
                     When provided, this takes precedence over string_value.
        create_empty_string: Whether to create an empty string value if string_value is empty. Default is False.
        create_empty_object: Whether to create an empty object value if object_value is empty. Default is False.
    
    Returns:
        A message indicating whether the operation was successful.
    """
    global driver
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        return f"Failed to initialize WebDriver: {str(e)}"
    
    try:
        # Determine the value to use
        if object_value or create_empty_object:
            # Convert the object to JSON string for storage
            json_value = json.dumps(object_value)
            # Need to properly escape quotes for JavaScript execution
            escaped_json = json_value.replace("'", "\\'").replace('"', '\\"')
            script = f"window.localStorage.setItem('{key}', JSON.stringify({json.dumps(object_value)}));"
        elif string_value or create_empty_string:
            # Check if string_value is a valid JSON string and handle accordingly
            try:
                # Try to parse as JSON to see if it's a JSON string
                json_obj = json.loads(string_value)
                # If it parses successfully, treat it as JSON
                script = f"window.localStorage.setItem('{key}', JSON.stringify({string_value}));"
            except json.JSONDecodeError:
                # Not valid JSON, treat as regular string
                script = f"window.localStorage.setItem('{key}', '{string_value}');"
        else:
            return f"No value provided for key '{key}'. Set create_empty_string or create_empty_object to True to create with empty value."
            
        driver.execute_script(script)
        logger.info("Ran script: %s", script)
        
        # Verify the item was added correctly
        verification_script = f"return window.localStorage.getItem('{key}');"
        stored_value = driver.execute_script(verification_script)
        
        return f"Successfully added key '{key}' to local storage with value: {stored_value}"
    
    except Exception as e:
        error_msg = f"Error adding to local storage: {str(e)}"
        logger.error(error_msg)
        return error_msg

@mcp.tool()
def local_storage_read(key: str) -> str:
    """Read a value from browser's local storage by key.
    
    This tool retrieves the value associated with the specified key from the browser's
    localStorage. If the key doesn't exist, it returns a message indicating the key was not found.
    
    Args:
        key: The key name of the local storage item to read.
    
    Returns:
        The value associated with the key, or a message if the key doesn't exist.
    """
    global driver
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        return f"Failed to initialize WebDriver: {str(e)}"
    
    try:
        # Execute JavaScript to get the value from local storage
        script = f"return window.localStorage.getItem('{key}');"
        value = driver.execute_script(script)
        
        if value is None:
            return f"Key '{key}' not found in local storage"
        else:
            return f"Value for key '{key}': {value}"
    
    except Exception as e:
        error_msg = f"Error reading from local storage: {str(e)}"
        logger.error(error_msg)
        return error_msg

@mcp.tool()
def local_storage_remove(key: str) -> str:
    """Remove a key-value pair from browser's local storage.
    
    This tool removes the specified key and its associated value from the browser's
    localStorage. If the key doesn't exist, it returns a message indicating the key was not found.
    
    Args:
        key: The key name of the local storage item to remove.
    
    Returns:
        A message indicating whether the operation was successful.
    """
    global driver
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        return f"Failed to initialize WebDriver: {str(e)}"
    
    try:
        # First check if the key exists
        check_script = f"return window.localStorage.getItem('{key}') !== null;"
        key_exists = driver.execute_script(check_script)
        
        if not key_exists:
            return f"Key '{key}' not found in local storage, nothing to remove"
        
        # Execute JavaScript to remove the item from local storage
        script = f"window.localStorage.removeItem('{key}');"
        driver.execute_script(script)
        
        # Verify the item was removed
        verification_script = f"return window.localStorage.getItem('{key}') === null;"
        was_removed = driver.execute_script(verification_script)
        
        if was_removed:
            return f"Successfully removed key '{key}' from local storage"
        else:
            return f"Error: Failed to remove key '{key}' from local storage"
    
    except Exception as e:
        error_msg = f"Error removing from local storage: {str(e)}"
        logger.error(error_msg)
        return error_msg

@mcp.tool()
def local_storage_read_all() -> str:
    """Read all key-value pairs from browser's local storage.
    
    This tool retrieves all items from the browser's localStorage and returns
    them as a dictionary. If localStorage is empty, it returns a message indicating
    that no items were found.
    
    Returns:
        A JSON string containing all localStorage items, or a message if localStorage is empty.
    """
    global driver
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        return f"Failed to initialize WebDriver: {str(e)}"
    
    try:
        # Execute JavaScript to get all items from local storage
        script = """
        const items = {};
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            items[key] = localStorage.getItem(key);
        }
        return items;
        """
        items = driver.execute_script(script)
        
        if not items:
            return "No items found in local storage"
        else:
            return json.dumps(items, indent=2)
    
    except Exception as e:
        error_msg = f"Error reading all items from local storage: {str(e)}"
        logger.error(error_msg)
        return error_msg

@mcp.tool()
def local_storage_remove_all() -> str:
    """Remove all key-value pairs from browser's local storage.
    
    This tool clears all items from the browser's localStorage. If localStorage
    is already empty, it returns a message indicating that there was nothing to remove.
    
    Returns:
        A message indicating whether the operation was successful.
    """
    global driver
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        return f"Failed to initialize WebDriver: {str(e)}"
    
    try:
        # First check if there are any items in localStorage
        count_script = "return localStorage.length;"
        item_count = driver.execute_script(count_script)
        
        if item_count == 0:
            return "Local storage is already empty, nothing to remove"
        
        # Execute JavaScript to clear all items from local storage
        script = "localStorage.clear(); return localStorage.length === 0;"
        success = driver.execute_script(script)
        
        if success:
            return f"Successfully removed all {item_count} item(s) from local storage"
        else:
            return "Error: Failed to clear local storage"
    
    except Exception as e:
        error_msg = f"Error removing all items from local storage: {str(e)}"
        logger.error(error_msg)
        return error_msg
