import logging
import os
import signal
import subprocess
import time
from typing import Optional, Any

logger = logging.getLogger(__name__)

class TimeoutException(Exception):
    pass

def get_chrome_version():
    """Get Chrome version from the system."""
    try:
        result = subprocess.run(['google-chrome', '--version'], 
                              capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            version = result.stdout.strip().split()[-1]
            return int(version.split('.')[0])
    except:
        pass
    return 130

try:
    import undetected_chromedriver as uc
    UC_AVAILABLE = True
except ImportError:
    uc = None
    webdriver = None
    UC_AVAILABLE = False


if UC_AVAILABLE:
    class UndetectedChromeDriver:
        """Undetected Chrome WebDriver implementation using undetected-chromedriver."""
        
        def __init__(self, user_data_dir: str = "", debug_port: int = 9222):
            self.user_data_dir = user_data_dir
            self.debug_port = debug_port
            self.driver: Optional[Any] = None
        
        def check_chrome_debugger_port(self) -> bool:
            """Check if Chrome is running with remote debugging port open"""
            # TODO: Implement chrome debugger port check for undetected chrome
            logger.warning("check_chrome_debugger_port not yet implemented for UndetectedChromeDriver")
            return False

        def start_chrome(self, custom_user_data_dir: str = "") -> bool:
            """Start Chrome with undetected-chromedriver"""
            # TODO: Implement chrome startup for undetected chrome
            logger.warning("start_chrome not yet implemented for UndetectedChromeDriver")
            return False

        def create_fast_driver(self, user_data_dir: str):
            """Create undetected_chromedriver with optimizations and local ChromeDriver"""
            
            # Get the path to the chromedriver binary
            script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            chromedriver_path = os.path.join(script_dir, "src", "mcp_server_selenium", "drivers", "chromedriver")
            
            # Setup Chrome options
            opts = uc.ChromeOptions()
            opts.add_argument(f'--user-data-dir={user_data_dir}')
            
            # Ultra-fast flags
            fast_flags = [
                '--no-sandbox',
                '--disable-dev-shm-usage', 
                '--disable-gpu',
                '--disable-extensions',
                '--disable-default-apps',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-logging',
                '--log-level=3',
                '--silent',
                '--window-size=1920,1080',  # Use reasonable window size for MCP server
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-features=VizDisplayCompositor',
                '--disable-ipc-flooding-protection'
            ]
            
            for flag in fast_flags:
                opts.add_argument(flag)
            
            # Get Chrome version for better compatibility
            chrome_version = get_chrome_version()
            logger.info(f"Detected Chrome version: {chrome_version}")
            
            # Setup timeout protection
            def alarm_handler(signum, frame):
                raise TimeoutException("Driver initialization timeout!")
            
            signal.signal(signal.SIGALRM, alarm_handler)
            signal.alarm(30)  # Increased timeout to 30 seconds for network operations
            
            try:
                logger.info("Attempting to create undetected Chrome driver...")
                
                # Method 1: Try with local ChromeDriver and detected version
                if os.path.exists(chromedriver_path):
                    logger.info(f"Using local ChromeDriver at: {chromedriver_path}")
                    try:
                        driver = uc.Chrome(
                            options=opts,
                            driver_executable_path=chromedriver_path,
                            use_subprocess=False,
                            version_main=chrome_version
                        )
                        signal.alarm(0)
                        logger.info("Successfully created driver with local ChromeDriver and detected version")
                        return driver
                    except Exception as e:
                        logger.warning(f"Failed with local ChromeDriver and detected version: {e}")
                
                # Method 2: Try with system ChromeDriver and detected version
                logger.info("Trying with system ChromeDriver and detected version...")
                try:
                    driver = uc.Chrome(
                        options=opts,
                        use_subprocess=False,
                        version_main=chrome_version
                    )
                    signal.alarm(0)
                    logger.info("Successfully created driver with system ChromeDriver and detected version")
                    return driver
                except Exception as e:
                    logger.warning(f"Failed with system ChromeDriver and detected version: {e}")
                
                # Method 3: Try with local ChromeDriver, no version detection (offline mode)
                if os.path.exists(chromedriver_path):
                    logger.info("Trying with local ChromeDriver in offline mode...")
                    try:
                        driver = uc.Chrome(
                            options=opts,
                            driver_executable_path=chromedriver_path,
                            use_subprocess=False,
                            version_main=chrome_version,
                            patcher_force_close=True  # Force close to avoid network calls
                        )
                        signal.alarm(0)
                        logger.info("Successfully created driver with local ChromeDriver in offline mode")
                        return driver
                    except Exception as e:
                        logger.warning(f"Failed with local ChromeDriver in offline mode: {e}")
                
                # Method 4: Last resort - system ChromeDriver with no version detection
                logger.info("Last resort: trying with system ChromeDriver, no version detection...")
                driver = uc.Chrome(
                    options=opts,
                    use_subprocess=False,
                    patcher_force_close=True
                )
                signal.alarm(0)
                logger.info("Successfully created driver with system ChromeDriver as last resort")
                return driver
                
            except Exception as e:
                signal.alarm(0)  # Cancel alarm
                logger.error(f"All driver creation methods failed: {e}")
                raise RuntimeError(f"Failed to create undetected Chrome driver: {e}")
            finally:
                signal.alarm(0)  # Ensure alarm is always cancelled

        def initialize_driver(self, custom_user_data_dir: str = ""):
            """Initialize and return an undetected Chrome WebDriver instance"""
            # Set user_data_dir if provided
            if custom_user_data_dir:
                self.user_data_dir = custom_user_data_dir
            
            # Use default user data dir if none provided
            if not self.user_data_dir:
                self.user_data_dir = "/tmp/selenium-mcp-chrome"
                os.makedirs(self.user_data_dir, exist_ok=True)
            
            logger.info("Initializing undetected Chrome driver with fast optimizations")
            
            try:
                start_time = time.time()
                
                # Create the optimized undetected chrome driver
                self.driver = self.create_fast_driver(self.user_data_dir)
                
                # Set longer page load timeout
                self.driver.set_page_load_timeout(120)
                self.driver.set_script_timeout(120)
                
                init_time = time.time()
                logger.info(f"Undetected Chrome driver initialized successfully in {init_time - start_time:.3f}s")
                return self.driver
                
            except Exception as e:
                logger.error(f"Failed to initialize undetected Chrome driver: {str(e)}")
                raise RuntimeError(f"Failed to initialize undetected Chrome driver: {str(e)}")

        def ensure_driver_initialized(self):
            """Ensure that the WebDriver is initialized.
            
            This function checks if the WebDriver instance is initialized.
            If not, it initializes a new WebDriver instance.
            
            Returns:
                The initialized WebDriver instance.
                
            Raises:
                RuntimeError: If the WebDriver fails to initialize.
            """
            if self.driver is None:
                logger.info("Undetected WebDriver is not initialized, initializing now...")
                try:
                    self.driver = self.initialize_driver(custom_user_data_dir=self.user_data_dir)
                    logger.info("Undetected WebDriver initialized successfully")
                except Exception as e:
                    logger.error(f"Failed to initialize undetected WebDriver: {str(e)}")
                    raise RuntimeError(f"Failed to initialize undetected WebDriver: {str(e)}")
            return self.driver
        
        def quit(self):
            """Quit the WebDriver instance."""
            if self.driver is not None:
                logger.info("Quitting undetected Chrome driver")
                self.driver.quit()
                self.driver = None

else:
    # Fallback class when undetected-chromedriver is not available
    class UndetectedChromeDriver:
        """Placeholder for UndetectedChromeDriver when package is not installed."""
        
        def __init__(self, user_data_dir: str = "", debug_port: int = 9222):
            raise ImportError(
                "undetected-chromedriver is not installed. "
                "Please install it with: pip install undetected-chromedriver"
            )
        
        def check_chrome_debugger_port(self) -> bool:
            raise ImportError("undetected-chromedriver is not available")

        def start_chrome(self, custom_user_data_dir: str = "") -> bool:
            raise ImportError("undetected-chromedriver is not available")

        def initialize_driver(self, custom_user_data_dir: str = "") -> Any:
            raise ImportError("undetected-chromedriver is not available")

        def ensure_driver_initialized(self) -> Any:
            raise ImportError("undetected-chromedriver is not available")
        
        def quit(self):
            raise ImportError("undetected-chromedriver is not available")