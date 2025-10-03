import json
import logging
from typing import Any, Dict, List
from urllib.parse import urlparse
from ..server import mcp, ensure_driver_initialized
from selenium import webdriver

logger = logging.getLogger(__name__)


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
        
        # Filter by URL text if specified (checks full URL, not just domain)
        if filter_url_by_text:
            logger.info(f"Filtering network logs by URL containing: {filter_url_by_text}")
            filtered_events = {}
            for request_id, events_list in grouped_events.items():
                # Check if any event in this group has a URL containing the filter text
                for event in events_list:
                    if 'url' in event:
                        try:
                            # Check both domain and full URL for flexibility
                            domain = urlparse(event['url']).netloc
                            full_url = event['url']
                            if filter_url_by_text in domain or filter_url_by_text in full_url:
                                filtered_events[request_id] = events_list
                                break
                        except Exception as e:
                            logger.error(f"Error parsing URL: {str(e)}")
            grouped_events = filtered_events
        
        # Convert dictionary to list of lists
        result = list(grouped_events.values())
        
        return result
    except Exception as e:
        logger.error(f"Error getting network logs from performance: {str(e)}")
        return []


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
        filter_url_by_text: Text to filter URLs by. When specified, only network
            requests with URLs containing this text (in either domain or path) will be included. 
            Default is empty string (no filtering). You should filter by domain or path because 
            the network logs can be numerous.
        only_errors_log: When True, only returns network requests with error status codes (4xx/5xx)
            or other network failures. Default is False (returns all network logs).
    
    Returns:
        A JSON string containing the network request logs, grouped by request ID.
    """
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