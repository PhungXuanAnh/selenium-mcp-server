#!/usr/bin/env python3
"""
Test script for the fixed undetected Chrome driver with improved error handling.
"""

import sys
import os
import time

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

def test_fixed_undetected_chrome():
    """Test the fixed undetected Chrome driver."""
    
    try:
        from mcp_server_selenium.drivers.undetected_chrome import UndetectedChromeDriver, UC_AVAILABLE
        
        if not UC_AVAILABLE:
            print("❌ undetected-chromedriver is not available")
            return False
        
        print("✅ undetected-chromedriver is available")
        print("🧪 Testing fixed UndetectedChromeDriver with improved error handling...")
        
        # Create driver instance
        start_time = time.time()
        driver_instance = UndetectedChromeDriver(user_data_dir="/tmp/test-selenium-mcp-fixed")
        
        # Initialize driver
        print("🚀 Initializing driver with multiple fallback methods...")
        driver = driver_instance.ensure_driver_initialized()
        
        init_time = time.time()
        print(f"⚡ Driver initialized in {init_time - start_time:.3f}s")
        
        # Test basic functionality
        print("🌐 Testing navigation to example.com...")
        driver.get("https://example.com")
        
        nav_time = time.time()
        print(f"📄 Page loaded in {nav_time - init_time:.3f}s")
        print(f"📑 Title: '{driver.title}'")
        
        # Test element finding
        try:
            h1_element = driver.find_element("tag name", "h1")
            print(f"🔍 H1 element found: '{h1_element.text}'")
        except Exception as e:
            print(f"⚠️  H1 element not found: {e}")
        
        total_time = time.time()
        print(f"🎉 Total test time: {total_time - start_time:.3f}s")
        print("✅ Fixed implementation test completed successfully!")
        
        # Clean up
        driver_instance.quit()
        print("🧹 Driver cleaned up")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_fixed_undetected_chrome()
    sys.exit(0 if success else 1)