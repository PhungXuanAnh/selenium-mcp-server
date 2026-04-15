import logging
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from datetime import datetime
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService

logger = logging.getLogger(__name__)


class NormalChromeDriver:
    """Normal Chrome WebDriver implementation."""
    
    def __init__(self, user_data_dir: str = "", debug_port: int = 9222, profile: str = "Default"):
        self.user_data_dir = user_data_dir
        self.debug_port = debug_port
        self.profile = profile
        self.driver: Optional[webdriver.Chrome] = None
    
    @staticmethod
    def _get_chromedriver_path() -> Optional[str]:
        """Return path to a compatible chromedriver, downloading to ~/.cache/selenium if needed.

        Uses the same cache location as selenium manager (~/.cache/selenium on all OSes).
        Bypasses selenium manager entirely to avoid its network-first lookup delays.
        """
        # Detect OS/arch -> Chrome for Testing platform string
        _machine = platform.machine().lower()
        _platform_map = {
            ("linux",  "x86_64"):  "linux64",
            ("linux",  "aarch64"): "linux-arm64",
            ("darwin", "x86_64"):  "mac-x64",
            ("darwin", "arm64"):   "mac-arm64",
            ("win32",  "amd64"):   "win64",
            ("win32",  "x86_64"):  "win64",
        }
        _plat = _platform_map.get((sys.platform, _machine))
        if not _plat:
            logger.warning(f"Unsupported platform ({sys.platform}/{_machine}); falling back to selenium manager")
            return None
        _exe = "chromedriver.exe" if sys.platform == "win32" else "chromedriver"

        # Detect installed Chrome version
        _chrome_cmds = ["google-chrome-stable", "google-chrome", "chromium-browser", "chromium"]
        if sys.platform == "darwin":
            _chrome_cmds.insert(0, "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        _chrome_version = None
        for _cmd in _chrome_cmds:
            try:
                _out = subprocess.run([_cmd, "--version"], capture_output=True, text=True, timeout=3).stdout
                _m = re.search(r"(\d+\.\d+\.\d+\.\d+)", _out)
                if _m:
                    _chrome_version = _m.group(1)
                    break
            except Exception:
                continue

        if not _chrome_version:
            logger.warning("Could not detect Chrome version; falling back to selenium manager")
            return None

        # Cache path: ~/.cache/selenium/chromedriver/{platform}/{version}/{exe}
        # This is the same path selenium manager uses on all OSes
        _cache_dir = os.path.join(
            os.path.expanduser("~"), ".cache", "selenium", "chromedriver", _plat, _chrome_version
        )
        _cache_path = os.path.join(_cache_dir, _exe)

        if os.path.isfile(_cache_path):
            logger.debug(f"Using cached chromedriver {_chrome_version} from {_cache_path}")
            return _cache_path

        # Not cached — download it ourselves
        _zip_name = f"chromedriver-{_plat}.zip"
        _url = f"https://storage.googleapis.com/chrome-for-testing-public/{_chrome_version}/{_plat}/{_zip_name}"
        _manual_cmd = (
            f"python -c \""
            f"import urllib.request,zipfile,os,shutil,tempfile; "
            f"t=tempfile.mkdtemp(); z=os.path.join(t,'cd.zip'); "
            f"urllib.request.urlretrieve('{_url}',z); "
            f"zf=zipfile.ZipFile(z); "
            f"m=[n for n in zf.namelist() if n.endswith('{_exe}')][0]; "
            f"zf.extract(m,t); "
            f"os.makedirs(r'{_cache_dir}',exist_ok=True); "
            f"shutil.copy(os.path.join(t,m),r'{_cache_path}'); "
            f"os.chmod(r'{_cache_path}',0o755); "
            f"print('Done')\""
        )

        _msg = f"chromedriver {_chrome_version} not in cache. Downloading from {_url} ..."
        logger.warning(_msg)
        print(_msg, flush=True)

        try:
            os.makedirs(_cache_dir, exist_ok=True)
            _zip_path = os.path.join(tempfile.mkdtemp(), "chromedriver.zip")
            _last_pct = [-1]

            def _progress(block_count, block_size, total_size):
                if total_size > 0:
                    pct = min(100, block_count * block_size * 100 // total_size)
                    rounded = (pct // 10) * 10
                    if rounded > _last_pct[0]:
                        _last_pct[0] = rounded
                        _p = f"Downloading chromedriver {_chrome_version}: {rounded}%"
                        logger.info(_p)
                        print(_p, flush=True)

            urllib.request.urlretrieve(_url, _zip_path, reporthook=_progress)

            with zipfile.ZipFile(_zip_path, "r") as zf:
                _members = [n for n in zf.namelist() if n.endswith(f"/{_exe}") or n == _exe]
                if not _members:
                    raise FileNotFoundError(f"{_exe} not found in zip")
                _tmp_dir = os.path.dirname(_zip_path)
                zf.extract(_members[0], _tmp_dir)
                shutil.copy(os.path.join(_tmp_dir, _members[0]), _cache_path)

            os.chmod(_cache_path, 0o755)

            # Remove old versions from cache (keep only the one we just downloaded)
            _parent = os.path.dirname(_cache_dir)  # .../chromedriver/{platform}/
            if os.path.isdir(_parent):
                for _old in os.listdir(_parent):
                    _old_path = os.path.join(_parent, _old)
                    if os.path.isdir(_old_path) and _old != _chrome_version:
                        shutil.rmtree(_old_path, ignore_errors=True)
                        logger.info(f"Removed old chromedriver cache: {_old_path}")

            _done = f"chromedriver {_chrome_version} saved to {_cache_path}"
            logger.info(_done)
            print(_done, flush=True)
            return _cache_path

        except Exception as dl_err:
            _err = f"Auto-download failed: {dl_err}. Download manually:\n  {_manual_cmd}"
            logger.error(_err)
            print(_err, flush=True)
            return None

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
                f"--profile-directory={self.profile}",
                "--no-first-run",
                "--no-default-browser-check",
                "--start-maximized",  # Start Chrome maximized
                "--auto-open-devtools-for-tabs"  # Auto-open DevTools for new tabs
            ]
            
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
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
                f"--profile-directory={self.profile}",
                "--no-first-run",
                "--no-default-browser-check",
                "--enable-logging",  # Enable logging
                "--start-maximized",  # Start Chrome maximized
                "--auto-open-devtools-for-tabs"  # Auto-open DevTools for new tabs
            ]
            
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
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
        
        # Resolve chromedriver from cache (downloading if needed) to bypass selenium manager
        _driver_path = self._get_chromedriver_path()
        service = ChromeService(executable_path=_driver_path) if _driver_path else ChromeService()
        
        # Create the driver
        self.driver = webdriver.Chrome(service=service, options=options)
        
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