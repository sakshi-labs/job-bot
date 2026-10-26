"""
Chrome Session Manager.
Launches Selenium Chrome with persistent user session profiles so that logins, cookies,
and 2FA sessions for Naukri, Hirist, and LinkedIn are maintained across runs without re-authenticating.
"""
import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

class ChromeSessionManager:
    @staticmethod
    def get_user_data_dir() -> str:
        """Returns the persistent bot profile directory."""
        bot_profile_dir = os.path.expanduser("~/.job_bot_chrome_profile")
        os.makedirs(bot_profile_dir, exist_ok=True)
        return bot_profile_dir

    @classmethod
    def create_driver(cls, headless: bool = False) -> webdriver.Chrome:
        """Creates a Chrome WebDriver instance maintaining saved logins and cookies."""
        options = Options()
        profile_path = cls.get_user_data_dir()
        
        options.add_argument(f"--user-data-dir={profile_path}")
        options.add_argument("--profile-directory=Default")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
        
        if headless:
            options.add_argument("--headless=new")

        # Exclude automation flags to avoid Cloudflare/bot detection
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        driver = webdriver.Chrome(options=options)
        return driver
