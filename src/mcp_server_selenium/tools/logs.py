import json
import logging
import time
from typing import Any, Dict, List
from urllib.parse import urlparse
from ..server import mcp, ensure_driver_initialized, auto_recover_stale_window
from selenium import webdriver

logger = logging.getLogger(__name__)
CONSOLE_LOG_DELIVERY_WAIT_SECONDS = 0.25


def read_driver_logs(
    driver: webdriver.Chrome,
    log_type: str,
    wait_seconds: float = 0,
) -> list[dict]:
    """Read a destructive WebDriver log buffer, briefly polling for delivery."""
    deadline = time.monotonic() + max(wait_seconds, 0)
    while True:
        try:
            entries = driver.get_log(log_type)
        except Exception as e:
            raise RuntimeError(f"Unable to read {log_type} logs: {e}") from e

        if entries or time.monotonic() >= deadline:
            return entries

        time.sleep(min(0.05, max(deadline - time.monotonic(), 0)))


def get_browser_logs(driver: webdriver.Chrome, log_type='browser'):
    """Get delivered browser logs and format them."""
    browser_logs = read_driver_logs(
        driver,
        log_type,
        wait_seconds=CONSOLE_LOG_DELIVERY_WAIT_SECONDS,
    )
    return [
        {
            'type': entry.get('level', 'INFO').lower(),
            'message': entry.get('message', ''),
            'timestamp': entry.get('timestamp', 0),
        }
        for entry in browser_logs
    ]


def process_performance_log_entry(entry):
    """Process a performance log entry to extract the message"""
    try:
        return json.loads(entry['message'])['message']
    except Exception as e:
        logger.error(f"Error processing performance log entry: {str(e)}")
        return {}


def get_performance_logs(driver: webdriver.Chrome):
    """Get raw performance logs from the driver

        ### 🔧 Background

        Each CDP event belongs to a **domain**, like:

        * `Network`
        * `Page`
        * `Runtime`
        * `Log`
        * `Performance`
        * `Console`
        * `DOM`
        * `Target`
        * `Security`
        * `Fetch`
        * `Storage`
        * `Tracing`
        * `Browser`
        * `Emulation`
        * `Input`
        * …and several others.

        So `msg["method"]` is of the form:

        ```
        <Domain>.<EventName>
        ```

        Example events:

        ```
        Network.requestWillBeSent
        Network.responseReceived
        Page.loadEventFired
        Page.domContentEventFired
        Runtime.consoleAPICalled
        Log.entryAdded
        Performance.metrics
        ```

        ---

        ### ⚙️ When using Selenium’s performance log (`get_log("performance")`)

        You’ll often see these domains:

        | Domain          | Common Events                                        | Purpose                  |
        | --------------- | ---------------------------------------------------- | ------------------------ |
        | **Network**     | requestWillBeSent, responseReceived, loadingFinished | All HTTP traffic         |
        | **Page**        | loadEventFired, domContentEventFired                 | Page lifecycle           |
        | **Runtime**     | consoleAPICalled, exceptionThrown                    | JS logs / errors         |
        | **Log**         | entryAdded                                           | Browser log entries      |
        | **Performance** | metrics                                              | Timing metrics           |
        | **Security**    | securityStateChanged                                 | HTTPS / certificate info |

        ---

        ### 🔍 So your filter

        ```python
        if msg.get("method", "").startswith("Network."):
        ```

        means you’re **only collecting network-related CDP events**, ignoring other domains like Page or Runtime.

        You could broaden your filter, for example:

        ```python
        if msg.get("method", "").startswith(("Network.", "Page.", "Runtime.")):
            ...
        ```

        ---

        ✅ **Summary**

        * The prefix before the dot (`Network`, `Page`, `Runtime`, …) is the **CDP domain**.
        * There are many domains; Selenium’s “performance” log can contain entries from any of them.
        * Filtering by `"Network."` is just a convenient way to isolate HTTP-level traffic events.

    """
    if driver is None:
        return []
    
    return read_driver_logs(driver, "performance")

def get_network_logs_from_performance_logs(driver: webdriver.Chrome, filter_url_by_text: str = '', only_errors_log: bool = False) -> List[Dict[str, Any]]:
    """Get network logs using performance logging"""
    if driver is None:
        return []
    
    try:
        # Get raw performance logs
        performance_logs = get_performance_logs(driver)
        if not performance_logs:
            return []

        # Process the logs to extract the message part
        network_events = []
        for entry in performance_logs:
            event = process_performance_log_entry(entry)
            if 'Network.' in event.get('method', ''):
                # Extract the relevant information
                params = event.get('params', {})
                request = params.get('request', {})
                response = params.get('response', {})
                event_url = request.get('url', '') or response.get('url', '')
                
                # Filter by URL text
                if filter_url_by_text and filter_url_by_text.strip() not in event_url:
                    continue
                
                if only_errors_log:
                    if params.get('response', {}).get("status", 0) < 400 and event.get('method') != 'Network.loadingFailed':
                        continue
                
                network_events.append(event)
                
                # # Create a simplified event object
                # if method == 'Network.requestWillBeSent':
                #     request = params.get('request', {})
                #     network_events.append({
                #         'type': 'request',
                #         'requestId': request_id,
                #         'method': request.get('method', ''),
                #         'url': request.get('url', ''),
                #         'timestamp': params.get('timestamp', 0),
                #         'headers': request.get('headers', {})
                #     })
                # elif method == 'Network.responseReceived':
                #     response = params.get('response', {})
                #     status = response.get('status', 0)
                #     status_text = response.get('statusText', '')
                    
                #     network_events.append({
                #         'type': 'response',
                #         'requestId': request_id,
                #         'status': status,
                #         'statusText': status_text,
                #         'url': response.get('url', ''),
                #         'timestamp': params.get('timestamp', 0),
                #         'headers': response.get('headers', {}),
                #         'mimeType': response.get('mimeType', ''),
                #         'hasError': status >= 400
                #     })
                # elif method == 'Network.loadingFailed':
                #     error_text = params.get('errorText', '')
                #     canceled = params.get('canceled', False)
                    
                #     network_events.append({
                #         'type': 'failed',
                #         'requestId': request_id,
                #         'errorText': error_text,
                #         'canceled': canceled,
                #         'timestamp': params.get('timestamp', 0),
                #         'hasError': True
                #     })
        
        return network_events
    except Exception as e:
        raise RuntimeError(f"Error getting network logs from performance logs: {e}") from e


@mcp.tool(description="Read and consume buffered browser console logs, optionally filtering by level.")
@auto_recover_stale_window
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
    normalized_log_level = log_level.strip().upper()
    if normalized_log_level == "ALL":
        normalized_log_level = ""
    elif normalized_log_level == "ERROR":
        normalized_log_level = "SEVERE"
    elif normalized_log_level not in {"", "DEBUG", "INFO", "WARNING", "SEVERE"}:
        return (
            "Error: log_level must be blank/ALL, DEBUG, INFO, WARNING, "
            "ERROR, or SEVERE"
        )

    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        return f"Failed to initialize WebDriver: {str(e)}"
    
    try:
        # Get browser logs
        logs = get_browser_logs(driver)
        
        # Filter logs by level if specified
        if normalized_log_level:
            logs = [
                log
                for log in logs
                if log['type'].upper() == normalized_log_level
            ]
        
        return json.dumps(logs, indent=2)
    except Exception as e:
        logger.error(f"Error getting console logs: {str(e)}")
        return f"Error getting console logs: {str(e)}"


@mcp.tool(description="Read and consume buffered performance events as network logs, optionally filtering by URL text or errors.")
@auto_recover_stale_window
def get_network_logs(filter_url_by_text: str = '', only_errors_log: bool = False) -> str:
    """Retrieve network request logs from the browser.
    
    This tool collects all network activity (requests and responses) that has occurred
    since the page was loaded. Results can optionally be filtered by domain.
    
    Args:
        filter_url_by_text: Text to filter URLs by. When specified, only network
            requests with URLs containing this text (in either domain or path) will be included. 
            Default is empty string (no filtering). You should filter by domain or path because 
            the network logs can be numerous.
        only_errors_log: When True, only returns network requests with error status codes (4xx/5xx)
            or other network failures. Default is False (returns all network logs).
    
    Returns:
        A JSON string containing the network request logs:
        📌 Main **Network events** you’ll see in `performance` logs:
        
        * **Request lifecycle**

        * `Network.requestWillBeSent` — a request is about to be sent (first point you can see URL, headers).
        * `Network.requestWillBeSentExtraInfo` — extra headers info (sometimes split for security reasons).
        * `Network.requestServedFromCache` — request was fulfilled from browser cache.

        * **Response lifecycle**

        * `Network.responseReceived` — headers/status arrived.
        * `Network.responseReceivedExtraInfo` — extra response header info.
        * `Network.dataReceived` — chunk of response data received.
        * `Network.loadingFinished` — all response data is received.
        * `Network.loadingFailed` — request failed (with reason).

        * **WebSocket / EventSource**

        * `Network.webSocketCreated`
        * `Network.webSocketWillSendHandshakeRequest`
        * `Network.webSocketHandshakeResponseReceived`
        * `Network.webSocketFrameSent`
        * `Network.webSocketFrameReceived`
        * `Network.webSocketClosed`
        * `Network.webSocketFrameError`

        * **Other network activity**

        * `Network.webTransportCreated`, `Network.webTransportClosed`
        * `Network.eventSourceMessageReceived`
        * `Network.signedExchangeReceived`
        * `Network.subresourceWebBundleMetadataReceived`
        * `Network.subresourceWebBundleMetadataError`
        * `Network.subresourceWebBundleInnerResponseParsed`
        * `Network.reportingApiReportAdded`, `Network.reportingApiReportUpdated`, `Network.reportingApiEndpointsChanged`
    """
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        return f"Failed to initialize WebDriver: {str(e)}"
    
    try:
        # Get network logs from performance data
        network_logs = get_network_logs_from_performance_logs(driver, filter_url_by_text, only_errors_log)
        return json.dumps(network_logs, indent=2)
    except Exception as e:
        logger.error(f"Error getting network logs: {str(e)}")
        return f"Error getting network logs: {str(e)}"
    

@mcp.tool(description="Fetch a response body by a request ID obtained from get_network_logs.")
@auto_recover_stale_window
def get_response(request_id: str) -> str:
    """Retrieve the full response body for a given network request ID.
    
    Args:
        request_id: The ID of the network request to retrieve the response for.
            It is got from Network.responseReceived event in performance logs
            from get_network_logs tool.
            
    Returns:
        A JSON string containing the response body and metadata, or an error message.
    """
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        return f"Failed to initialize WebDriver: {str(e)}"
    
    try:
        if not request_id:
            return "request_id parameter is required."
        
        # Use CDP command to get response body
        response = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
        # Main **Network commands** (things you can call via CDP)
        # Examples:
        # * `Network.enable`, `Network.disable`
        # * `Network.getResponseBody`
        # * `Network.setExtraHTTPHeaders`
        # * `Network.setUserAgentOverride`
        # * `Network.emulateNetworkConditions`
        # * `Network.clearBrowserCache`, `Network.clearBrowserCookies`
        # * `Network.setBlockedURLs`
        # * `Network.getCookies`, `Network.setCookie`, `Network.deleteCookies`
        
        return json.dumps(response, indent=2)
    except Exception as e:
        logger.error(f"Error getting response body for request ID {request_id}: {str(e)}")
        return f"Error getting response body for request ID {request_id}: {str(e)}"
