import json
import logging
from ..server import mcp, ensure_driver_initialized

logger = logging.getLogger(__name__)


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