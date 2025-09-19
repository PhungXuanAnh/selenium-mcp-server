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


def test_selenium():
    navigate("https://google.com")


if __name__ == "__main__":
    try:
        test_selenium()
    except Exception as e:
        print(f"Error during test: {str(e)}")
        import traceback
        traceback.print_exc()