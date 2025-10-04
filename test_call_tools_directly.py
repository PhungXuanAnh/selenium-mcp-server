"""
Run this command to test calling the tools directly:
.venv/bin/python -i test_call_tools_directly.py
it will attach to python interactive mode after running the script
and you can call the functions directly like:
>>> test_get_style_an_element()
or
>>> test_get_style_an_element(element_type="p", all_styles=False, computed_style=False)
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



def test_undetected_chrome():
    """Test the optimized undetected Chrome driver."""
    
    try:
        from mcp_server_selenium.drivers.undetected_chrome import UndetectedChromeDriver, UC_AVAILABLE
        
        if not UC_AVAILABLE:
            print("❌ undetected-chromedriver is not available")
            return False
        
        print("✅ undetected-chromedriver is available")
        print("🧪 Testing optimized UndetectedChromeDriver...")
        
        # Create driver instance
        start_time = time.time()
        driver_instance = UndetectedChromeDriver(user_data_dir="/tmp/test-selenium-mcp")
        
        # Initialize driver
        print("🚀 Initializing driver...")
        driver = driver_instance.ensure_driver_initialized()
        
        init_time = time.time()
        print(f"⚡ Driver initialized in {init_time - start_time:.3f}s")
        
        # Test navigation
        print("🌐 Testing navigation to Google...")
        driver.get("https://www.google.com")
        
        nav_time = time.time()
        print(f"📄 Page loaded in {nav_time - init_time:.3f}s")
        print(f"📑 Title: '{driver.title}'")
        
        # Test element finding (basic functionality check)
        try:
            search_box = driver.find_element("name", "q")
            print("🔍 Search box found successfully")
        except Exception as e:
            print(f"⚠️  Search box not found: {e}")
        
        total_time = time.time()
        print(f"🎉 Total test time: {total_time - start_time:.3f}s")
        print("✅ Test completed successfully!")
        
        # Clean up
        driver_instance.quit()
        print("🧹 Driver cleaned up")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


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

def test_get_network_logs(filter_url_by_text=""):
    """Test getting network logs."""
    print("Testing get_network_logs function...")
    print("=" * 50)

    # First try without any filter to see all logs
    print("Getting all network logs (no filter)...")
    result_all = get_network_logs()
    import json
    # print(f"All Network Logs:\n{result_all}")
    

if __name__ == "__main__":
    driver = initialize_driver_instance(custom_user_data_dir="/tmp/google-chrome-selenium-mcp-direct")
    # Test navigation first
    test_navigate()
    
    # Wait a moment for page to fully load
    import time
    time.sleep(3)
    
    # Test page ready check
    test_check_page_ready()
    
    # Test network logs (only once since logs are cleared after reading)
    test_get_network_logs()
    
    