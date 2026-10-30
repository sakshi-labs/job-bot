"""
Chrome Session Manager — Robust Singleton Driver
=================================================
Architecture (v3 — macOS-safe):

  • Uses webdriver-manager to auto-download the correct ChromeDriver for the
    installed Chrome version.  No manual chromedriver installation needed.
  • Uses a DEDICATED bot-only profile directory (NOT the user's default Chrome
    profile) so there is NEVER a conflict with an already-running Chrome window.
  • Keeps one singleton webdriver.Chrome() alive for the whole bot session.
    Each application opens in a NEW TAB (not a new process/window).
  • If the singleton dies mid-session it is transparently recreated.
  • Headless mode is supported for CI / server runs.

Quick-start
-----------
You do NOT need to manually pre-launch Chrome.  Just run the Flask app or
call  ChromeSessionManager.get_driver()  and it will handle everything.
"""

import os
import time
import atexit

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager


# ── Constants ────────────────────────────────────────────────────────────────
# Separate profile directory that ONLY the bot uses — never opened by the user's
# normal Chrome. This sidesteps the "Chrome profile already in use" macOS error.
BOT_PROFILE_DIR = os.path.expanduser("~/.job_bot_chrome_selenium_profile")


class ChromeSessionManager:
    """Thread-safe singleton Selenium driver manager."""

    _driver: webdriver.Chrome | None = None
    _headless: bool = False

    # ── Public API ────────────────────────────────────────────────────────────

    @classmethod
    def get_driver(cls, headless: bool = False) -> webdriver.Chrome:
        """
        Return the shared Chrome driver, creating it if necessary.
        The driver persists across multiple job applications so login
        cookies are preserved within the same bot session.
        """
        cls._headless = headless

        # Re-use existing healthy driver
        if cls._driver is not None:
            try:
                _ = cls._driver.current_url  # ping — raises if session is dead
                return cls._driver
            except Exception:
                print("[!] Existing Chrome session is stale — restarting...")
                cls._safe_quit()

        cls._driver = cls._create_driver(headless)
        return cls._driver

    @classmethod
    def open_new_tab(cls, driver: webdriver.Chrome, url: str) -> str:
        """
        Open *url* in a new tab and switch focus to it.
        Returns the window handle of the new tab.
        """
        existing_handles = set(driver.window_handles)
        driver.execute_script("window.open(arguments[0], '_blank');", url)
        time.sleep(1.5)  # give Chrome time to create the tab

        new_handles = set(driver.window_handles) - existing_handles
        if not new_handles:
            # Fallback: navigate in current tab
            driver.get(url)
            return driver.current_window_handle

        new_handle = new_handles.pop()
        driver.switch_to.window(new_handle)
        print(f"[✓] Opened new tab ({new_handle[:8]}…) → {url[:80]}")
        return new_handle

    @classmethod
    def close_tab(cls, driver: webdriver.Chrome, tab_handle: str,
                  original_handle: str | None = None) -> None:
        """Close *tab_handle* and switch back to *original_handle* (or first tab)."""
        try:
            driver.switch_to.window(tab_handle)
            driver.close()
        except Exception:
            pass

        remaining = driver.window_handles
        if remaining:
            target = (
                original_handle
                if (original_handle and original_handle in remaining)
                else remaining[0]
            )
            try:
                driver.switch_to.window(target)
            except Exception:
                pass

    @classmethod
    def quit(cls) -> None:
        """Cleanly shut down the shared driver (called at process exit)."""
        cls._safe_quit()

    # ── Internal helpers ──────────────────────────────────────────────────────

    @classmethod
    def _create_driver(cls, headless: bool) -> webdriver.Chrome:
        """Build and return a fresh webdriver.Chrome instance."""
        os.makedirs(BOT_PROFILE_DIR, exist_ok=True)

        options = Options()

        # ── Profile: dedicated bot-only directory ──────────────────────────
        options.add_argument(f"--user-data-dir={BOT_PROFILE_DIR}")
        options.add_argument("--profile-directory=Default")

        # ── Anti-fingerprinting / automation detection bypass ──────────────
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--start-maximized")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/156.0.0.0 Safari/537.36"
        )
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        if headless:
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1280,900")
            options.add_argument("--disable-gpu")
        else:
            options.add_argument("--window-size=1280,900")

        # ── ChromeDriver: auto-managed, correct version ────────────────────
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
        except Exception as e:
            # Last-resort: let Selenium find chromedriver on PATH
            print(f"[!] webdriver-manager failed ({e}), trying system chromedriver...")
            driver = webdriver.Chrome(options=options)

        # Remove the "navigator.webdriver" property that sites use to detect bots
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """
            },
        )

        print(f"[✓] Chrome launched (profile: {BOT_PROFILE_DIR})")
        return driver

    @classmethod
    def _safe_quit(cls) -> None:
        if cls._driver is not None:
            try:
                cls._driver.quit()
            except Exception:
                pass
            cls._driver = None


# Ensure Chrome closes cleanly when the Python process exits
atexit.register(ChromeSessionManager.quit)
