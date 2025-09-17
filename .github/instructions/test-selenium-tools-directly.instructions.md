---
applyTo: '**'
---
Provide project context and coding guidelines that AI should follow when generating code, answering questions, or reviewing changes.# Testing Selenium Tools Directly

This document provides examples of how to call selenium MCP server tools directly from Python code without using the MCP protocol. This is useful for testing, debugging, or integrating the tools into other Python applications.

## Prerequisites

Before running these examples, make sure you have:
1. Chrome browser installed
2. The selenium MCP server dependencies installed
3. A Chrome instance running with remote debugging enabled (the server will handle this automatically)

## Setup Code

First, you need to set up the Python path and import the necessary modules:

```python
import sys
import os
import json

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

# Import the tools you want to use
from mcp_server_selenium.tools.navigate import navigate
from mcp_server_selenium.tools.page_ready import check_page_ready
from mcp_server_selenium.tools.logs import get_console_logs, get_network_logs
from mcp_server_selenium.tools.style import get_style_an_element
from mcp_server_selenium.tools.element_interaction import get_an_element, click_to_element
from mcp_server_selenium.tools.screenshot import take_screenshot
```

## Example 1: Basic Navigation and Page Ready Check

```python
# Navigate to Google
print("=== Navigating to Google ===")
navigate_result = navigate(url="https://www.google.com")
print(f"Navigation result: {navigate_result}")

# Check if page is ready
print("\n=== Checking if page is ready ===")
page_ready_result = check_page_ready()
print(f"Page ready result: {page_ready_result}")

# Wait a bit and check again
import time
time.sleep(2)
page_ready_result = check_page_ready()
print(f"Page ready result after 2 seconds: {page_ready_result}")
```

## Example 2: Getting Browser Logs

```python
# Get console logs (all levels)
print("\n=== Getting all console logs ===")
console_logs = get_console_logs()
print(f"Console logs: {console_logs}")

# Get only error logs
print("\n=== Getting only error console logs ===")
error_logs = get_console_logs(log_level="ERROR")
print(f"Error logs: {error_logs}")

# Get network logs (filtered by domain)
print("\n=== Getting network logs for google.com ===")
network_logs = get_network_logs(filter_url_by_text="google.com")
print(f"Network logs: {network_logs}")

# Get only error network logs
print("\n=== Getting only error network logs ===")
error_network_logs = get_network_logs(only_errors_log=True)
print(f"Error network logs: {error_network_logs}")
```

## Example 3: Element Interaction and Styling

```python
# Find the search input box on Google
print("\n=== Finding Google search input ===")
search_input = get_an_element(element_type="input", attributes={"name": "q"})
print(f"Search input element: {search_input}")

# Get style information for the search input
print("\n=== Getting style information for search input ===")
search_input_styles = get_style_an_element(
    element_type="input", 
    attributes={"name": "q"},
    all_styles=True,
    computed_style=True
)
print(f"Search input styles: {search_input_styles}")

# Click on the search input (to focus it)
print("\n=== Clicking on search input ===")
click_result = click_to_element(element_type="input", attributes={"name": "q"})
print(f"Click result: {click_result}")
```

## Example 4: Taking Screenshots

```python
# Take a screenshot
print("\n=== Taking screenshot ===")
screenshot_result = take_screenshot()
print(f"Screenshot result: {screenshot_result}")
```

## Complete Example Script

Here's a complete script that combines all the examples above:

```python
#!/usr/bin/env python3
"""
Complete example of calling selenium MCP tools directly.
Run this script from the selenium-mcp-server root directory.
"""

import sys
import os
import json
import time

# Setup path
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

# Import tools
from mcp_server_selenium.tools.navigate import navigate
from mcp_server_selenium.tools.page_ready import check_page_ready
from mcp_server_selenium.tools.logs import get_console_logs, get_network_logs
from mcp_server_selenium.tools.style import get_style_an_element
from mcp_server_selenium.tools.element_interaction import get_an_element, click_to_element
from mcp_server_selenium.tools.screenshot import take_screenshot

def main():
    """Main function to run all examples."""
    
    try:
        # Step 1: Navigate to Google
        print("=== Step 1: Navigating to Google ===")
        result = navigate(url="https://www.google.com")
        print(f"Navigation result: {result}")
        
        # Step 2: Check page ready
        print("\n=== Step 2: Checking if page is ready ===")
        time.sleep(2)  # Wait a bit for page to load
        result = check_page_ready()
        print(f"Page ready: {result}")
        
        # Step 3: Get browser logs
        print("\n=== Step 3: Getting browser console logs ===")
        logs = get_console_logs()
        print(f"Console logs: {logs}")
        
        # Step 4: Get network logs
        print("\n=== Step 4: Getting network logs ===")
        network_logs = get_network_logs(filter_url_by_text="google")
        print(f"Network logs (google domain): {network_logs}")
        
        # Step 5: Find and style search input
        print("\n=== Step 5: Finding search input and getting styles ===")
        search_element = get_an_element(element_type="input", attributes={"name": "q"})
        print(f"Search element: {search_element}")
        
        styles = get_style_an_element(
            element_type="input", 
            attributes={"name": "q"},
            all_styles=True,
            computed_style=True
        )
        print(f"Search input styles: {styles}")
        
        # Step 6: Take screenshot
        print("\n=== Step 6: Taking screenshot ===")
        screenshot = take_screenshot()
        print(f"Screenshot: {screenshot}")
        
        print("\n=== All steps completed successfully! ===")
        
    except Exception as e:
        print(f"Error during execution: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
```

## Running the Examples

To run these examples:

1. Make sure you're in the selenium-mcp-server root directory
2. Save any of the example code to a Python file (e.g., `test_direct_calls.py`)
3. Run it with: `python test_direct_calls.py`

## Notes

- The selenium driver will be automatically initialized when you call the first tool
- Make sure Chrome is available on your system
- The tools will handle iframe switching, error handling, and driver management automatically
- All results are returned as JSON strings that you can parse if needed
- Screenshots are saved to the `~/selenium-mcp/screenshot/` directory

## Common Use Cases

1. **Testing**: Use these direct calls to test individual tools during development
2. **Debugging**: Call tools directly to debug issues without the MCP protocol overhead
3. **Integration**: Integrate selenium functionality into other Python applications
4. **Automation**: Create custom automation scripts using the selenium tools as building blocks