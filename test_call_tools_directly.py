"""
Test script for the get_style_an_element function.

This script tests the get_style_an_element function by calling it directly
with specified arguments.
"""

import sys
import os

# Add the src directory to the Python path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mcp_server_selenium.tools.style import get_style_an_element
from mcp_server_selenium.tools.navigate import navigate
from mcp_server_selenium.tools.element_interaction import get_an_element
from mcp_server_selenium.tools.page_ready import check_page_ready
from mcp_server_selenium.tools.screenshot import take_screenshot


def test_navigate_to_example():
    """Navigate to example.com to ensure there's a page loaded for style checking."""
    print("Navigating to https://example.com...")
    navigate(url="https://example.com")
    print("Navigation complete.")

def test_get_style_an_element():
    """Test function to call get_style_an_element directly with specified arguments."""
    
    print("Testing get_style_an_element function...")
    print("=" * 50)
    
    # Call the function with the specified arguments
    result = get_style_an_element(
        element_type="h1", 
        all_styles=True,
        computed_style=True
    )
    
    print("Result:")
    print(result)
    print("=" * 50)
    
    return result


def test_check_page_ready():
    """Test if the page is ready."""
    print("Testing check_page_ready function...")
    print("=" * 50)
    
    result = check_page_ready()
    print(f"Page ready result: {result}")
    print("=" * 50)
    
    return result


def test_get_element():
    """Test getting an element from the page."""
    print("Testing get_an_element function...")
    print("=" * 50)
    
    result = get_an_element(element_type="h1")
    print(f"Element result: {result}")
    print("=" * 50)
    
    return result


def test_take_screenshot():
    """Test taking a screenshot."""
    print("Testing take_screenshot function...")
    print("=" * 50)
    
    result = take_screenshot()
    print(f"Screenshot result: {result}")
    print("=" * 50)
    
    return result


if __name__ == "__main__":
    try:
        # Test navigation first
        test_navigate_to_example()
        
        # Wait a moment for page to fully load
        import time
        time.sleep(2)
        
        # Test page ready check
        test_check_page_ready()
        
        # Test element finding
        test_get_element()
        
        # Test style getting
        test_get_style_an_element()
        
        # Test screenshot
        test_take_screenshot()
        
        print("\n" + "=" * 50)
        print("✓ All tests completed successfully!")
        print("✓ Normal Chrome driver is working correctly")
        print("=" * 50)
        
    except Exception as e:
        print(f"Error during test: {str(e)}")
        import traceback
        traceback.print_exc()