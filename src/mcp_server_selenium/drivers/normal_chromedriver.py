import logging
import socket
import subprocess
import time
from datetime import datetime
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions

logger = logging.getLogger(__name__)


class NormalChromeDriver:
    """Normal Chrome WebDriver implementation."""
    
    def __init__(self, user_data_dir: str = "", debug_port: int = 9222):
        self.user_data_dir = user_data_dir
        self.debug_port = debug_port
        self.driver: Optional[webdriver.Chrome] = None
    
    def check_chrome_debugger_port(self) -> bool:
        """Check if Chrome is running with remote debugging port open"""
        try:
            # Try to connect to the port
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('127.0.0.1', self.debug_port))
                return result == 0
        except Exception as e:
            logger.error(f"Error checking Chrome debugger port: {str(e)}")
            return False

    def start_chrome(self, custom_user_data_dir: str = "") -> bool:
        """Start Chrome with remote debugging enabled on specified port"""
        try:
            if custom_user_data_dir:
                self.user_data_dir = custom_user_data_dir
            elif not self.user_data_dir:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.user_data_dir = f"/tmp/chrome-debug-{timestamp}"
            
            logger.info(f"Starting Chrome with debugging port {self.debug_port} and user data dir {self.user_data_dir}")
            
            # Start Chrome as a subprocess
            cmd = [
                "google-chrome-stable",
                f"--remote-debugging-port={self.debug_port}",
                f"--user-data-dir={self.user_data_dir}",
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
            if self.check_chrome_debugger_port():
                logger.info(f"Chrome started successfully on port {self.debug_port}")
                return True
            else:
                logger.error("Failed to start Chrome or confirm debugging port is open")
                return False
        except Exception as e:
            logger.error(f"Error starting Chrome: {str(e)}")
            return False

    def initialize_driver(self, custom_user_data_dir: str = "") -> webdriver.Chrome:
        """Initialize and return a WebDriver instance based on browser choice"""
        
        # Set user_data_dir if provided
        if custom_user_data_dir:
            self.user_data_dir = custom_user_data_dir
        
        # Check if Chrome is already running with remote debugging
        if not self.check_chrome_debugger_port():
            logger.info(f"Chrome not detected on port {self.debug_port}, attempting to start a new instance")
            
            # Start Chrome with DevTools auto-open
            if not self.user_data_dir:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.user_data_dir = f"/tmp/chrome-debug-{timestamp}"
            
            logger.info(f"Starting Chrome with debugging port {self.debug_port} and user data dir {self.user_data_dir}")
            
            # Start Chrome as a subprocess with DevTools auto-open
            cmd = [
                "google-chrome-stable",
                f"--remote-debugging-port={self.debug_port}",
                f"--user-data-dir={self.user_data_dir}",
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
            
            if not self.check_chrome_debugger_port():
                raise RuntimeError("Failed to start Chrome browser")
        else:
            logger.info(f"Chrome already running with remote debugging port {self.debug_port}")
        
        # Setup capabilities to enable browser logging
        options = ChromeOptions()
        options.debugger_address = f"127.0.0.1:{self.debug_port}"
        
        # Set logging preferences for both browser logs and performance logs
        options.set_capability('goog:loggingPrefs', {
            'browser': 'ALL',
            'performance': 'ALL'
        })
        
        # Create the driver
        self.driver = webdriver.Chrome(options=options)
        
        # Maximize the window
        self.driver.maximize_window()
        
        # Set longer page load timeout
        self.driver.set_page_load_timeout(120)
        self.driver.set_script_timeout(120)
        
        return self.driver

    def ensure_driver_initialized(self) -> webdriver.Chrome:
        """Ensure that the WebDriver is initialized.
        
        This function checks if the WebDriver instance is initialized.
        If not, it initializes a new WebDriver instance.
        
        Returns:
            The initialized WebDriver instance.
            
        Raises:
            RuntimeError: If the WebDriver fails to initialize.
        """
        if self.driver is None:
            logger.info("WebDriver is not initialized, initializing now...")
            try:
                self.driver = self.initialize_driver(custom_user_data_dir=self.user_data_dir)
                logger.info("WebDriver initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize WebDriver: {str(e)}")
                raise RuntimeError(f"Failed to initialize WebDriver: {str(e)}")
        return self.driver
    
    def quit(self):
        """Quit the WebDriver instance."""
        if self.driver is not None:
            logger.info("Disconnecting from Chrome instance (but leaving browser open)")
            self.driver.quit()
            self.driver = None