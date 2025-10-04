"""
Test script for the get_style_an_element function.

This script tests the get_style_an_element function by calling it directly
with specified arguments.
"""

import sys
import os

# Add the src directory to the Python path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mcp_server_selenium.server import initialize_driver_instance
from mcp_server_selenium.tools.style import get_style_an_element
from mcp_server_selenium.tools.navigate import navigate
from mcp_server_selenium.tools.element_interaction import get_an_element
from mcp_server_selenium.tools.page_ready import check_page_ready
from mcp_server_selenium.tools.screenshot import take_screenshot
from mcp_server_selenium.tools.logs import get_network_logs

def test_navigate(url="https://example.com"):
    """Navigate to example.com to ensure there's a page loaded for style checking."""
    print(f"Navigating to {url}...")
    navigate(url=url)
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

def test_get_network_logs_and_classify(filter_url_by_text=""):
    """Test getting network logs."""
    print("Testing get_network_logs function...")
    print("=" * 50)

    # First try without any filter to see all logs
    print("Getting all network logs (no filter)...")
    result_all = get_network_logs()
    try:
        import json
        logs_data = json.loads(result_all) if result_all.startswith('[') else []
        print(f"All network logs count: {len(logs_data)}")
        
        # Let's examine some URLs to understand the filtering issue
        if logs_data:
            print("\nSample URLs found in logs:")
            url_count = 0
            for request_group in logs_data[:5]:  # Look at first 5 request groups
                for event in request_group:
                    if 'url' in event and event['url']:
                        print(f"  - {event['url']}")
                        url_count += 1
                        if url_count >= 10:  # Limit to 10 URLs
                            break
                if url_count >= 10:
                    break
                    
            # Look for specific API URLs
            api_requests = []
            for request_group in logs_data:
                for event in request_group:
                    if 'url' in event and 'api/internal/apps' in event['url']:
                        api_requests.append(event['url'])
            
            print(f"\nAPI requests found: {len(api_requests)}")
            for api_url in api_requests[:3]:
                print(f"  - {api_url}")
                
    except Exception as e:
        print(f"Failed to parse network logs as JSON: {e}")
        logs_data = []
    
    print("=" * 50)
    return result_all


if __name__ == "__main__":
    driver = initialize_driver_instance(custom_user_data_dir="/tmp/google-chrome-selenium-mcp-direct")
    # Test navigation first
    test_navigate()
    
    # Wait a moment for page to fully load
    import time
    time.sleep(5)
    
    # Test page ready check
    test_check_page_ready()
    
    # Test network logs (only once since logs are cleared after reading)
    test_get_network_logs_and_classify()
    
    