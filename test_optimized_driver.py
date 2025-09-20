#!/usr/bin/env python3
"""
Test script for the updated undetected Chrome driver with optimizations.
"""

import sys
import os
import time

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

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

if __name__ == "__main__":
    success = test_undetected_chrome()
    sys.exit(0 if success else 1)