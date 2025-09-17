import json
import logging
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

# Global variable to store WebDriver instance
driver: Optional[webdriver.Chrome] = None

# Global variable for Chrome user data directory
user_data_dir: str = ""

# Global variable for Chrome debugging port
debug_port: int = 9222

# Initialize FastMCP
mcp = FastMCP(
    name="mcp-selenium-sync",
)


def check_chrome_debugger_port() -> bool:
    """Check if Chrome is running with remote debugging port open"""
    global debug_port
    try:
        # Try to connect to the port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('127.0.0.1', debug_port))
            return result == 0
    except Exception as e:
        logger.error(f"Error checking Chrome debugger port: {str(e)}")
        return False


def start_chrome(custom_user_data_dir: str = "") -> bool:
    """Start Chrome with remote debugging enabled on specified port"""
    global user_data_dir
    global debug_port
    try:
        if custom_user_data_dir:
            user_data_dir = custom_user_data_dir
        elif not user_data_dir:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            user_data_dir = f"/tmp/chrome-debug-{timestamp}"
        
        logger.info(f"Starting Chrome with debugging port {debug_port} and user data dir {user_data_dir}")
        
        # Start Chrome as a subprocess
        cmd = [
            "google-chrome-stable",
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--start-maximized",  # Start Chrome maximized
            "--auto-open-devtools-for-tabs"  # Auto-open DevTools for new tabs
        ]
        
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            start_new_session=True  # Detach from the parent process
        )
        
        # Wait a moment for Chrome to start
        time.sleep(3)
        
        # Check if Chrome started correctly
        if check_chrome_debugger_port():
            logger.info(f"Chrome started successfully on port {debug_port}")
            return True
        else:
            logger.error("Failed to start Chrome or confirm debugging port is open")
            return False
    except Exception as e:
        logger.error(f"Error starting Chrome: {str(e)}")
        return False


def initialize_driver(custom_user_data_dir: str = "") -> webdriver.Chrome:
    """Initialize and return a WebDriver instance based on browser choice"""
    global driver
    global user_data_dir
    global debug_port
    
    # Set user_data_dir if provided
    if custom_user_data_dir:
        user_data_dir = custom_user_data_dir
    
    # Check if Chrome is already running with remote debugging
    if not check_chrome_debugger_port():
        logger.info(f"Chrome not detected on port {debug_port}, attempting to start a new instance")
        
        # Start Chrome with DevTools auto-open
        if not user_data_dir:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            user_data_dir = f"/tmp/chrome-debug-{timestamp}"
        
        logger.info(f"Starting Chrome with debugging port {debug_port} and user data dir {user_data_dir}")
        
        # Start Chrome as a subprocess with DevTools auto-open
        cmd = [
            "google-chrome-stable",
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--enable-logging",  # Enable logging
            "--start-maximized",  # Start Chrome maximized
            "--auto-open-devtools-for-tabs"  # Auto-open DevTools for new tabs
        ]
        
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            start_new_session=True  # Detach from the parent process
        )
        
        # Wait a moment for Chrome to start
        time.sleep(3)
        
        if not check_chrome_debugger_port():
            raise RuntimeError("Failed to start Chrome browser")
    else:
        logger.info(f"Chrome already running with remote debugging port {debug_port}")
    
    # Setup capabilities to enable browser logging
    options = ChromeOptions()
    options.debugger_address = f"127.0.0.1:{debug_port}"
    
    # Set logging preferences for both browser logs and performance logs
    options.set_capability('goog:loggingPrefs', {
        'browser': 'ALL',
        'performance': 'ALL'
    })
    
    # Create the driver
    driver = webdriver.Chrome(options=options)
    
    # Maximize the window
    driver.maximize_window()
    
    # Set longer page load timeout
    driver.set_page_load_timeout(120)
    driver.set_script_timeout(120)
    
    return driver


def ensure_driver_initialized() -> webdriver.Chrome:
    """Ensure that the WebDriver is initialized.
    
    This function checks if the global WebDriver instance is initialized.
    If not, it initializes a new WebDriver instance.
    
    Returns:
        The initialized WebDriver instance.
        
    Raises:
        RuntimeError: If the WebDriver fails to initialize.
    """
    global driver
    global user_data_dir
    
    if driver is None:
        logger.info("WebDriver is not initialized, initializing now...")
        try:
            driver = initialize_driver(custom_user_data_dir=user_data_dir)
            logger.info("WebDriver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {str(e)}")
            raise RuntimeError(f"Failed to initialize WebDriver: {str(e)}")
    return driver
