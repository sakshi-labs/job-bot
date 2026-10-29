"""
Chrome Session Manager.
Re-uses an existing Chrome window by attaching to a running Chrome debug instance
via the Chrome DevTools Protocol (CDP) remote-debugging port.

HOW IT WORKS
------------
1.  The user starts Chrome ONCE with --remote-debugging-port=9222 (see run instructions).
2.  Every subsequent call to ChromeSessionManager.get_driver() CONNECTS to that existing
    window rather than spawning a new browser process.
3.  Applications are opened in a NEW TAB within the existing window, preserving all
    logged-in sessions (LinkedIn, Naukri, Hirist, etc.) and cookies.
4.  When a tab's work is finished it is closed, leaving the original window intact.

STARTING CHROME WITH REMOTE DEBUGGING
--------------------------------------
Run this ONCE before starting the bot:

    /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
        --remote-debugging-port=9222 \
        --user-data-dir=/Users/sakshimalik/.job_bot_chrome_profile \
        --no-first-run \
        --no-default-browser-check

Or use the helper method:
    ChromeSessionManager.launch_debug_chrome()
"""

import os
import subprocess
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException


REMOTE_DEBUG_PORT = 9222
USER_DATA_DIR = os.path.expanduser("~/.job_bot_chrome_profile")
CHROME_APP = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


class ChromeSessionManager:
    _driver: webdriver.Chrome | None = None  # shared singleton driver

    @staticmethod
    def get_user_data_dir() -> str:
        os.makedirs(USER_DATA_DIR, exist_ok=True)
        return USER_DATA_DIR

    @classmethod
    def launch_debug_chrome(cls) -> None:
        """
        Launches Chrome with remote-debugging enabled.
        Call this once before the bot starts if Chrome is not already running.
        """
        os.makedirs(USER_DATA_DIR, exist_ok=True)
        cmd = [
            CHROME_APP,
            f"--remote-debugging-port={REMOTE_DEBUG_PORT}",
            f"--user-data-dir={USER_DATA_DIR}",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[*] Chrome launched with remote-debugging on port {REMOTE_DEBUG_PORT}.")
        print(f"[*] Profile directory: {USER_DATA_DIR}")
        time.sleep(2)  # give Chrome time to start

    @classmethod
    def get_driver(cls, headless: bool = False) -> webdriver.Chrome:
        """
        Returns a Selenium driver connected to the already-running Chrome instance.
        Falls back to launching a fresh Chrome process if no debug instance is found.
        """
        # ── Try attaching to an existing Chrome remote-debugging session ──
        options = Options()
        options.add_experimental_option(
            "debuggerAddress", f"127.0.0.1:{REMOTE_DEBUG_PORT}"
        )
        # Anti-detection
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        try:
            driver = webdriver.Chrome(options=options)
            print(f"[✓] Attached to existing Chrome session via CDP port {REMOTE_DEBUG_PORT}.")
            return driver
        except WebDriverException as e:
            print(f"[!] Could not attach to existing Chrome ({e}).")
            print(f"[*] Falling back to launching a fresh Chrome instance with persistent profile...")

        # ── Fallback: fresh Chrome with persistent profile ──
        fallback_opts = Options()
        fallback_opts.add_argument(f"--user-data-dir={USER_DATA_DIR}")
        fallback_opts.add_argument("--profile-directory=Default")
        fallback_opts.add_argument("--start-maximized")
        fallback_opts.add_argument("--disable-blink-features=AutomationControlled")
        fallback_opts.add_argument(
            "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        fallback_opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        fallback_opts.add_experimental_option("useAutomationExtension", False)

        if headless:
            fallback_opts.add_argument("--headless=new")

        driver = webdriver.Chrome(options=fallback_opts)
        print(f"[✓] Launched new Chrome window with persistent profile: {USER_DATA_DIR}")
        return driver

    @classmethod
    def open_new_tab(cls, driver: webdriver.Chrome, url: str) -> str:
        """
        Opens `url` in a new tab inside the existing Chrome window.
        Returns the handle of the new tab so the caller can close it later.
        """
        original_handles = set(driver.window_handles)
        driver.execute_script(f"window.open('{url}', '_blank');")
        time.sleep(1)

        new_handles = set(driver.window_handles) - original_handles
        if not new_handles:
            # Fallback: just navigate current tab
            driver.get(url)
            return driver.current_window_handle

        new_handle = new_handles.pop()
        driver.switch_to.window(new_handle)
        print(f"[✓] Opened new tab ({new_handle}) for: {url}")
        return new_handle

    @classmethod
    def close_tab(cls, driver: webdriver.Chrome, tab_handle: str,
                  original_handle: str | None = None) -> None:
        """Closes the given tab and switches focus back to `original_handle` (or first tab)."""
        try:
            driver.switch_to.window(tab_handle)
            driver.close()
        except Exception:
            pass

        remaining = driver.window_handles
        if remaining:
            target = original_handle if (original_handle and original_handle in remaining) else remaining[0]
            driver.switch_to.window(target)
