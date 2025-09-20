import json
import logging
from ..server import mcp, ensure_driver_initialized

logger = logging.getLogger(__name__)


@mcp.tool()
def run_javascript_in_console(javascript_code: str) -> str:
    """Execute JavaScript code in the browser console.
    
    This tool allows you to run JavaScript code directly in the browser console.
    The code can be multiple lines and can perform various operations like:
    - DOM manipulation
    - Variable creation and modification
    - Function calls
    - Console output
    - Retrieving data from the page
    
    Args:
        javascript_code: The JavaScript code to execute. Can be single or multiple lines.
                        Use semicolons to separate statements or newlines for better readability.
    
    Returns:
        The result of the JavaScript execution. If the script returns a value,
        it will be converted to a string. If there's an error, the error message
        will be returned.
    """
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        raise RuntimeError(str(e))
    
    logger.info(f"Executing JavaScript code in console")
    logger.debug(f"JavaScript code: {javascript_code}")
    
    try:
        # Execute the JavaScript code
        result = driver.execute_script(javascript_code)
        
        # Handle different types of results
        if result is None:
            return "JavaScript executed successfully (no return value)"
        elif isinstance(result, (str, int, float, bool)):
            return f"JavaScript executed successfully. Result: {result}"
        elif isinstance(result, (list, dict)):
            # Convert complex objects to JSON for better readability
            try:
                return f"JavaScript executed successfully. Result: {json.dumps(result, indent=2)}"
            except (TypeError, ValueError):
                # Fallback if JSON serialization fails
                return f"JavaScript executed successfully. Result: {str(result)}"
        else:
            return f"JavaScript executed successfully. Result: {str(result)}"
            
    except Exception as e:
        error_msg = f"Error executing JavaScript: {str(e)}"
        logger.error(error_msg)
        return error_msg


@mcp.tool()
def run_javascript_and_get_console_output(javascript_code: str) -> str:
    """Execute JavaScript code and capture both the return value and console output.
    
    This tool runs JavaScript code and captures any console.log, console.warn, console.error
    messages along with the return value. Useful for debugging and seeing all output.
    
    Args:
        javascript_code: The JavaScript code to execute. Can include console.log statements.
    
    Returns:
        A formatted string containing both the execution result and any console output.
    """
    try:
        driver = ensure_driver_initialized()
    except RuntimeError as e:
        raise RuntimeError(str(e))
    
    logger.info(f"Executing JavaScript code with console output capture")
    logger.debug(f"JavaScript code: {javascript_code}")
    
    try:
        # Clear any existing console logs first
        driver.get_log('browser')
        
        # Execute the JavaScript code
        result = driver.execute_script(javascript_code)
        
        # Get console logs that were generated during execution
        console_logs = []
        try:
            browser_logs = driver.get_log('browser')
            for log_entry in browser_logs:
                if log_entry['source'] == 'console-api':
                    console_logs.append({
                        'level': log_entry['level'],
                        'message': log_entry['message'],
                        'timestamp': log_entry['timestamp']
                    })
        except Exception as log_error:
            logger.warning(f"Could not retrieve console logs: {log_error}")
        
        # Format the response
        response_parts = []
        
        # Add execution result
        if result is None:
            response_parts.append("Execution Result: undefined")
        elif isinstance(result, (list, dict)):
            try:
                response_parts.append(f"Execution Result: {json.dumps(result, indent=2)}")
            except (TypeError, ValueError):
                response_parts.append(f"Execution Result: {str(result)}")
        else:
            response_parts.append(f"Execution Result: {result}")
        
        # Add console output if any
        if console_logs:
            response_parts.append("\nConsole Output:")
            for log in console_logs:
                timestamp = log['timestamp']
                level = log['level']
                message = log['message']
                response_parts.append(f"  [{level}] {message}")
        else:
            response_parts.append("\nConsole Output: (no console output captured)")
        
        return "\n".join(response_parts)
            
    except Exception as e:
        error_msg = f"Error executing JavaScript: {str(e)}"
        logger.error(error_msg)
        return error_msg