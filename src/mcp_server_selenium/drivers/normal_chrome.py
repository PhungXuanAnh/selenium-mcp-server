import json
import logging
import os
import platform
import re
import shutil
import signal
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
    
    def __init__(self, user_data_dir: str = "", profile: str = "Default"):
        self.user_data_dir = user_data_dir
        self.debug_port = 0
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

    def _port_file_path(self) -> Optional[str]:
        """Path to a file that records the debug port for this user_data_dir."""
        if self.user_data_dir:
            return os.path.join(self.user_data_dir, ".selenium_debug_port")
        return None

    def _is_chrome_on_port(self, port: int, check_user_data_dir: bool = False) -> bool:
        """Verify a port belongs to Chrome, optionally with matching user_data_dir.

        1. Hits http://127.0.0.1:{port}/json/version to confirm Chrome DevTools.
        2. If check_user_data_dir is True, inspects process command line to
           confirm --user-data-dir matches self.user_data_dir.
        """
        # Step 1: Confirm it's Chrome via DevTools Protocol
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/json/version")
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read())
            browser = data.get("Browser", "")
            if "Chrome" not in browser and "Chromium" not in browser:
                logger.debug(f"Port {port} is not Chrome (Browser={browser!r})")
                return False
        except Exception:
            return False

        # Step 2: Verify user_data_dir via process command line
        if not check_user_data_dir or not self.user_data_dir:
            return True

        port_flag = f"--remote-debugging-port={port}"
        dir_flag = f"--user-data-dir={self.user_data_dir}"
        try:
            if sys.platform == "linux":
                for entry in os.listdir("/proc"):
                    if not entry.isdigit():
                        continue
                    try:
                        with open(f"/proc/{entry}/cmdline", "rb") as f:
                            cmdline = f.read().decode("utf-8", errors="replace")
                        if port_flag in cmdline and dir_flag in cmdline:
                            return True
                    except (PermissionError, FileNotFoundError, ProcessLookupError):
                        continue
            else:
                # macOS / Windows: use ps or trust the DevTools check
                result = subprocess.run(
                    ["ps", "aux"], capture_output=True, text=True, timeout=3
                )
                for line in result.stdout.splitlines():
                    if port_flag in line and dir_flag in line:
                        return True
        except Exception:
            return True  # If process inspection fails, trust the DevTools check

        logger.debug(f"Chrome on port {port} does not use user_data_dir={self.user_data_dir}")
        return False

    def _find_chrome_port_by_user_data_dir(self) -> Optional[int]:
        """Find the debug port of a running Chrome that uses self.user_data_dir.

        Scans process command lines for --user-data-dir=<our dir> and extracts
        --remote-debugging-port=<N>.  Returns the port if found and DevTools
        responds on it, otherwise None.
        """
        if not self.user_data_dir:
            return None

        dir_flag = f"--user-data-dir={self.user_data_dir}"
        port_re = re.compile(r"--remote-debugging-port=(\d+)")

        candidates: list[int] = []
        try:
            if sys.platform == "linux":
                for entry in os.listdir("/proc"):
                    if not entry.isdigit():
                        continue
                    try:
                        with open(f"/proc/{entry}/cmdline", "rb") as f:
                            cmdline = f.read().decode("utf-8", errors="replace")
                        if dir_flag not in cmdline:
                            continue
                        m = port_re.search(cmdline)
                        if m:
                            candidates.append(int(m.group(1)))
                    except (PermissionError, FileNotFoundError, ProcessLookupError):
                        continue
            else:
                result = subprocess.run(
                    ["ps", "aux"], capture_output=True, text=True, timeout=3
                )
                for line in result.stdout.splitlines():
                    if dir_flag in line:
                        m = port_re.search(line)
                        if m:
                            candidates.append(int(m.group(1)))
        except Exception:
            return None

        # Verify each candidate via DevTools Protocol
        for port in candidates:
            if self._is_chrome_on_port(port, check_user_data_dir=True):
                logger.info(
                    f"Discovered running Chrome on port {port} for {self.user_data_dir}"
                )
                return port
        return None

    def _kill_chrome_with_user_data_dir(self) -> bool:
        """Kill Chrome processes using self.user_data_dir (e.g. started without debug port).

        This is needed when Chrome is running with our user_data_dir but was not
        started with --remote-debugging-port, so we cannot connect to it and
        cannot start a new instance (Chrome locks the user data dir).
        Sends SIGTERM first, then SIGKILL after 5 s if still alive.
        Returns True if at least one process was killed.
        """
        if not self.user_data_dir:
            return False

        dir_flag = f"--user-data-dir={self.user_data_dir}"
        pids: list[int] = []

        try:
            if sys.platform == "linux":
                for entry in os.listdir("/proc"):
                    if not entry.isdigit():
                        continue
                    try:
                        with open(f"/proc/{entry}/cmdline", "rb") as f:
                            cmdline = f.read().decode("utf-8", errors="replace")
                        if dir_flag in cmdline and ("chrome" in cmdline.lower() or "chromium" in cmdline.lower()):
                            pids.append(int(entry))
                    except (PermissionError, FileNotFoundError, ProcessLookupError):
                        continue
            else:
                result = subprocess.run(
                    ["ps", "aux"], capture_output=True, text=True, timeout=3
                )
                for line in result.stdout.splitlines():
                    if dir_flag in line and ("chrome" in line.lower() or "chromium" in line.lower()):
                        parts = line.split()
                        if len(parts) > 1 and parts[1].isdigit():
                            pids.append(int(parts[1]))
        except Exception:
            return False

        if not pids:
            return False

        logger.warning(
            f"Found Chrome process(es) {pids} using {self.user_data_dir} without "
            f"a debug port we can connect to. Killing to free the user data dir."
        )

        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                continue
            except PermissionError:
                logger.error(f"No permission to kill PID {pid}")
                continue

        # Wait up to 5 s for graceful shutdown, then SIGKILL stragglers
        for _ in range(10):
            time.sleep(0.5)
            alive = []
            for pid in pids:
                try:
                    os.kill(pid, 0)  # Check if still alive
                    alive.append(pid)
                except ProcessLookupError:
                    pass
            if not alive:
                break
            pids = alive
        else:
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGKILL)
                    logger.warning(f"Sent SIGKILL to PID {pid}")
                except (ProcessLookupError, PermissionError):
                    pass
            time.sleep(1)

        logger.info("Killed Chrome process(es) that were blocking the user data dir")
        return True

    def _read_saved_port(self) -> Optional[int]:
        """Read a previously saved debug port and verify it's Chrome with our user_data_dir."""
        pf = self._port_file_path()
        if pf and os.path.isfile(pf):
            try:
                with open(pf) as f:
                    port = int(f.read().strip())
                if self._is_chrome_on_port(port, check_user_data_dir=True):
                    return port
            except (ValueError, OSError):
                pass
        return None

    def _save_port(self) -> None:
        """Save the current debug port to the user_data_dir."""
        pf = self._port_file_path()
        if pf:
            try:
                os.makedirs(os.path.dirname(pf), exist_ok=True)
                with open(pf, "w") as f:
                    f.write(str(self.debug_port))
            except OSError:
                pass

    def check_chrome_debugger_port(self) -> bool:
        """Check if Chrome is running with remote debugging port open.

        Verifies via Chrome DevTools Protocol endpoint, not just TCP.
        """
        return self._is_chrome_on_port(self.debug_port)

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
                self._save_port()
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
        
        # Auto-detect port: saved file -> process scan -> allocate new
        saved = self._read_saved_port()
        if saved:
            self.debug_port = saved
            logger.info(f"Found existing Chrome on port {saved} for {self.user_data_dir}")
        else:
            # Port file missing/stale — scan running processes for Chrome
            # with our user_data_dir (handles port file out-of-sync)
            discovered = self._find_chrome_port_by_user_data_dir()
            if discovered:
                self.debug_port = discovered
                self._save_port()  # Update the stale port file
            else:
                # No Chrome with debug port found — kill any non-debug Chrome
                # that locks our user_data_dir before starting a fresh one
                self._kill_chrome_with_user_data_dir()
                from mcp_server_selenium.server import find_available_port
                self.debug_port = find_available_port()
                logger.info(f"Auto-detected available port: {self.debug_port}")
        
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
            self._save_port()
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
        try:
            self.driver.maximize_window()
        except Exception:
            pass  # Already maximized or window state not changeable
        
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