"""
Master Application Bot Orchestrator (v3).
=========================================
Coordinates JD parsing, resume tailoring, ATS PDF generation, and automated form filling.

KEY FIXES IN v3:
  1. HTTP HEAD pre-check before launching browser — dead 404/expired links are
     instantly skipped with clear error_reason. No wasted browser time.
  2. ChromeSessionManager is a true singleton: ONE Chrome window opens per bot
     session, not per application. Each job gets a new TAB, not a new window.
  3. webdriver-manager auto-installs the correct ChromeDriver for Chrome 156.
     The user does NOT need to manually install chromedriver or pre-launch Chrome.
  4. Status is ONLY "applied" when the form was CONFIRMED submitted.
     All other outcomes → "not_applied" with a human-readable error_reason.
  5. After form pre-fill the tab stays OPEN so you can review and manually
     submit. An /api/hunter/mark-applied/<job_id> endpoint lets you confirm.
  6. Applied job URLs tracked in output/applied_registry.json (dedup).
"""

import os
import re
import json
import time
from typing import Optional, Dict, Any

import requests as http_requests  # renamed to avoid collision with flask's request

from .models import JobDescription, TailoredResume
from .jd_parser import JDParser
from .tailor import ResumeTailor
from .ats_pdf import ATSPdfGenerator
from .html_generator import generate_html_resume
from .chrome_session import ChromeSessionManager
from .forms.greenhouse import GreenhouseFormFiller
from .forms.lever import LeverFormFiller
from .forms.ashby import AshbyFormFiller
from .forms.workday import WorkdayFormFiller
from .forms.generic import GenericFormFiller


# ─── Applied Job Registry ────────────────────────────────────────────────────

def _load_applied_registry(registry_path: str) -> set:
    """Loads the set of URLs/IDs we have already successfully applied to."""
    if os.path.exists(registry_path):
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return set(data) if isinstance(data, list) else set()
        except Exception:
            pass
    return set()


def _save_applied_registry(registry_path: str, registry: set) -> None:
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(sorted(list(registry)), f, indent=2)


# ─── HTTP URL validator ──────────────────────────────────────────────────────

def _is_url_alive(url: str, timeout: int = 8) -> tuple[bool, int]:
    """
    Does a lightweight HEAD request to check if the URL is accessible.
    Returns (is_alive, http_status_code).
    """
    try:
        resp = http_requests.head(
            url,
            allow_redirects=True,
            timeout=timeout,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/156.0.0.0 Safari/537.36"
                )
            },
        )
        # Some servers redirect HEAD to a login page — treat 200/201/301/302 as alive
        if resp.status_code in (200, 201, 301, 302, 303):
            return True, resp.status_code
        if resp.status_code in (404, 410, 400):
            return False, resp.status_code
        # For anything else (403, 429, 500…) assume alive — let browser decide
        return True, resp.status_code
    except Exception:
        # Network error, timeout, SSL error → assume alive (browser will show real error)
        return True, 0


# ─── Bot ─────────────────────────────────────────────────────────────────────

class JobApplicationBot:
    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.profile_path = os.path.join(config_dir, "master_profile.json")
        self.settings_path = os.path.join(config_dir, "settings.json")

        self.profile = {}
        if os.path.exists(self.profile_path):
            with open(self.profile_path, "r", encoding="utf-8") as f:
                self.profile = json.load(f)

        self.settings = {}
        if os.path.exists(self.settings_path):
            with open(self.settings_path, "r", encoding="utf-8") as f:
                self.settings = json.load(f)

        self.jd_parser = JDParser()
        self.tailor = ResumeTailor(self.profile_path, self.settings_path)
        self.pdf_generator = ATSPdfGenerator()

        # Registry of successfully applied job URLs — prevents re-applying
        output_dir = self.settings.get("output_dir", "output")
        os.makedirs(output_dir, exist_ok=True)
        self._registry_path = os.path.abspath(
            os.path.join(config_dir, "..", output_dir, "applied_registry.json")
        )
        self.applied_registry: set = _load_applied_registry(self._registry_path)

    # ── Tailoring ─────────────────────────────────────────────────────────────

    def process_and_tailor(
        self,
        jd_input: str,
        is_url: bool = False,
        profile: Optional[Dict[str, Any]] = None,
        customizations: Optional[Dict[str, Any]] = None,
    ) -> TailoredResume:
        """Parses JD and generates a tailored resume PDF + HTML."""
        if is_url or jd_input.startswith("http://") or jd_input.startswith("https://"):
            print(f"[*] Fetching job posting from: {jd_input}")
            jd = self.jd_parser.parse_from_url(jd_input)
        elif os.path.isfile(jd_input):
            print(f"[*] Reading job description from file: {jd_input}")
            with open(jd_input, "r", encoding="utf-8") as f:
                content = f.read()
            jd = self.jd_parser.parse_from_text(content)
        else:
            jd = self.jd_parser.parse_from_text(jd_input)

        active_prof = profile or self.profile
        print(
            f"[*] Tailoring resume for '{jd.title}' at '{jd.company}' "
            f"(profile: {active_prof.get('profile_name', 'master')})..."
        )

        tailored = self.tailor.tailor(jd, profile=active_prof, customizations=customizations)
        print(f"[+] Tailoring complete! ATS Match Score: {tailored.ats_score}%")

        safe_company = re.sub(r"[^a-zA-Z0-9]", "_", tailored.target_company.lower()).strip("_")
        safe_role = re.sub(r"[^a-zA-Z0-9]", "_", tailored.target_role.lower()).strip("_")
        out_dir = self.settings.get("output_dir", "output")
        os.makedirs(out_dir, exist_ok=True)

        pdf_path = os.path.abspath(os.path.join(out_dir, f"resume_{safe_company}_{safe_role}.pdf"))
        html_path = os.path.abspath(os.path.join(out_dir, f"resume_{safe_company}_{safe_role}.html"))

        self.pdf_generator.generate(tailored, pdf_path)
        generate_html_resume(tailored, html_path)

        tailored.pdf_path = pdf_path
        tailored.html_path = html_path
        return tailored

    # ── Application Automation ────────────────────────────────────────────────

    def apply_to_job(
        self,
        job_url: str,
        tailored_resume: TailoredResume,
        job_id: str = "",
        review_mode: bool = False,
        interactive: bool = False,
    ) -> Dict[str, Any]:
        """
        Opens job_url in a NEW TAB of the shared Chrome window, detects the ATS,
        fills the application form, and returns an accurate status report.

        Status values
        -------------
        "applied"     → Confirmed submitted (auto_submit=true and submit button clicked)
        "prefilled"   → Form fields filled, tab left open for manual review + submit
        "not_applied" → Login wall / expired link / URL dead / duplicate / error
        """
        # ── Guard: URL format ────────────────────────────────────────────────
        if not job_url or not (
            job_url.startswith("http://") or job_url.startswith("https://")
        ):
            return {
                "status": "not_applied",
                "error_reason": f"Invalid URL: '{job_url}'",
                "fields_filled": [],
                "job_url": job_url,
            }

        # ── Guard: duplicate ─────────────────────────────────────────────────
        dedup_key = job_id or job_url
        if dedup_key in self.applied_registry:
            print(f"[⚠] Already applied to {dedup_key} — skipping duplicate.")
            return {
                "status": "not_applied",
                "error_reason": "Already applied to this opening in a previous session.",
                "fields_filled": [],
                "job_url": job_url,
                "duplicate": True,
            }

        # ── Guard: HTTP pre-check (fast dead-link detection) ─────────────────
        print(f"[*] Pre-checking URL reachability: {job_url[:80]}")
        alive, http_status = _is_url_alive(job_url)
        if not alive:
            reason = (
                f"Job posting no longer available — server returned HTTP {http_status}. "
                "The listing was probably removed by the recruiter."
            )
            print(f"[✗] {reason}")
            return {
                "status": "not_applied",
                "error_reason": reason,
                "fields_filled": [],
                "job_url": job_url,
            }

        # ── Acquire shared Chrome driver ─────────────────────────────────────
        headless = (
            not review_mode
            and self.settings.get("browser", {}).get("headless", False)
        )
        try:
            driver = ChromeSessionManager.get_driver(headless=headless)
        except Exception as e:
            print(f"[✗] Could not start Chrome: {e}")
            return {
                "status": "not_applied",
                "error_reason": (
                    f"Chrome could not start: {e}. "
                    "Make sure Google Chrome is installed at "
                    "/Applications/Google Chrome.app and try again."
                ),
                "fields_filled": [],
                "job_url": job_url,
            }

        original_handle = driver.window_handles[0] if driver.window_handles else None
        new_tab_handle = None
        report: Dict[str, Any] = {"fields_filled": [], "job_url": job_url}

        try:
            # ── Open job URL in a new tab ─────────────────────────────────────
            new_tab_handle = ChromeSessionManager.open_new_tab(driver, job_url)

            timeout_s = self.settings.get("browser", {}).get("timeout_ms", 30000) / 1000
            driver.set_page_load_timeout(timeout_s)
            time.sleep(2.5)  # let JS-rendered pages settle

            page_source = driver.page_source.lower()
            current_url = driver.current_url
            print(f"[*] Page loaded → {current_url[:80]}")

            # ── Detect login walls ────────────────────────────────────────────
            login_signals = [
                "sign in to apply",
                "log in to apply",
                "create an account to apply",
                "you must be logged in",
                "please log in",
                "login required",
                "sign up to apply",
                "join linkedin",
                "authwall",
                "sign in to continue",
            ]
            if any(sig in page_source for sig in login_signals):
                reason = (
                    "Login wall detected. Please open the browser that the bot launched "
                    "(~/.job_bot_chrome_selenium_profile), log into this portal manually, "
                    "then click 1-Click Apply again. The bot will reuse your session."
                )
                print(f"[⚠] Login wall — {current_url[:60]}")
                report["status"] = "not_applied"
                report["error_reason"] = reason
                return report

            # ── Detect expired / removed postings ────────────────────────────
            expired_signals = [
                "job no longer available",
                "this job has expired",
                "position has been filled",
                "job not found",
                "this position has been closed",
                "no longer accepting applications",
                "404",
                "page not found",
                "page doesn't exist",
                "sorry, we couldn't find that page",
            ]
            if any(sig in page_source for sig in expired_signals):
                reason = "Job posting is expired or has been removed by the recruiter."
                print(f"[⚠] Expired posting — {current_url[:60]}")
                report["status"] = "not_applied"
                report["error_reason"] = reason
                return report

            # ── ATS Detection ─────────────────────────────────────────────────
            filler = None
            raw_source = driver.page_source  # original-case for filler.is_match
            if WorkdayFormFiller.is_match(current_url, raw_source):
                print("[*] ATS detected: Workday")
                filler = WorkdayFormFiller()
            elif GreenhouseFormFiller.is_match(current_url, raw_source):
                print("[*] ATS detected: Greenhouse")
                filler = GreenhouseFormFiller()
            elif LeverFormFiller.is_match(current_url, raw_source):
                print("[*] ATS detected: Lever")
                filler = LeverFormFiller()
            elif AshbyFormFiller.is_match(current_url, raw_source):
                print("[*] ATS detected: Ashby")
                filler = AshbyFormFiller()
            else:
                print("[*] ATS detected: Generic / Custom Career Page")
                filler = GenericFormFiller()

            # ── Fill form ─────────────────────────────────────────────────────
            print("[*] Filling form fields...")
            fill_result = filler.fill(driver, self.profile, tailored_resume.pdf_path)

            filled = fill_result.get("fields_filled", [])
            unhandled = fill_result.get("unhandled_questions", [])
            report["fields_filled"] = filled
            report["unhandled_questions"] = unhandled

            if filled:
                print(f"[+] Fields pre-filled: {', '.join(filled)}")
            else:
                print("[~] No standard fields detected — tab is open for manual fill")
            if unhandled:
                print(f"[~] Unhandled questions require manual input: {'; '.join(str(u) for u in unhandled)}")

            # ── Submission logic ──────────────────────────────────────────────
            auto_submit = self.settings.get("browser", {}).get("auto_submit", False)

            if review_mode and interactive:
                # CLI review: user presses Enter after manual submit
                print("\n" + "=" * 65)
                print(">>> REVIEW MODE — FORM PRE-FILLED <<<")
                print("Review and SUBMIT in the Chrome window, then press [ENTER].")
                print("Type 'skip' to skip this application.")
                print("=" * 65)
                try:
                    user_input = input().strip().lower()
                    if user_input in ("skip", "no", "n"):
                        report["status"] = "not_applied"
                        report["error_reason"] = "Skipped by user during review."
                        return report
                except Exception:
                    pass
                report["status"] = "applied"
                report["error_reason"] = None

            elif auto_submit:
                # Fully automatic: click Submit if detected
                submitted = self._attempt_submit(driver)
                if submitted:
                    print("[+] Form submitted automatically ✓")
                    report["status"] = "applied"
                    report["error_reason"] = None
                else:
                    report["status"] = "prefilled"
                    report["error_reason"] = (
                        "auto_submit=true but no Submit button was found. "
                        "Form is pre-filled — open the tab and submit manually."
                    )

            else:
                # Default safe mode: pre-fill and leave tab open for human review
                print(
                    "[ℹ] Form pre-filled. Tab is OPEN in Chrome — "
                    "please review and click Submit manually. "
                    "Then click '✓ Mark as Applied' in the dashboard."
                )
                report["status"] = "prefilled"
                report["error_reason"] = (
                    "Form pre-filled — please review in Chrome and submit manually. "
                    "Click '✓ Mark as Applied' in the dashboard after submitting."
                )

            # ── Register confirmed submissions ────────────────────────────────
            if report.get("status") == "applied":
                self.applied_registry.add(dedup_key)
                _save_applied_registry(self._registry_path, self.applied_registry)
                print(f"[✓] '{dedup_key}' added to applied registry.")

            return report

        except Exception as e:
            print(f"[✗] Automation error: {e}")
            return {
                "status": "not_applied",
                "error_reason": f"Automation error: {e}",
                "fields_filled": report.get("fields_filled", []),
                "job_url": job_url,
            }
        finally:
            # Keep tab open when pre-filled (for manual review).
            # Close ONLY if definitely not applied or if auto-submitted.
            if new_tab_handle:
                status = report.get("status", "")
                if status in ("applied", "not_applied"):
                    # Confirmed done or hard error — close tab
                    try:
                        ChromeSessionManager.close_tab(driver, new_tab_handle, original_handle)
                        print(f"[*] Closed automation tab.")
                    except Exception:
                        pass
                else:
                    # "prefilled" — leave tab open for user to review
                    print("[ℹ] Tab left open in Chrome for manual review.")

    # ── Manual mark-as-applied ────────────────────────────────────────────────

    def mark_as_applied(self, job_id: str, job_url: str = "") -> None:
        """
        Called when the user manually confirms they submitted the application.
        Adds job_id (and optionally job_url) to the applied registry.
        """
        dedup_key = job_id or job_url
        if dedup_key:
            self.applied_registry.add(dedup_key)
            _save_applied_registry(self._registry_path, self.applied_registry)
            print(f"[✓] '{dedup_key}' manually marked as applied in registry.")

    # ── Submit button detection ───────────────────────────────────────────────

    def _attempt_submit(self, driver) -> bool:
        """
        Tries common submit button CSS selectors.
        Returns True if a visible, enabled submit button was clicked.
        """
        from selenium.webdriver.common.by import By

        selectors = [
            # Workday
            "button[data-automation-id='bottom-navigation-next-button']",
            "button[data-automation-id='bottom-navigation-done-button']",
            # Generic
            "button[type='submit']",
            "input[type='submit']",
            "button#submit-app",
            "button.submit",
            "button[aria-label*='submit' i]",
            "button[aria-label*='apply now' i]",
            "button[aria-label*='submit application' i]",
            # Greenhouse
            "#submit_app",
            "input#submit",
        ]
        for sel in selectors:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                try:
                    if el.is_displayed() and el.is_enabled():
                        el.click()
                        time.sleep(1.5)
                        return True
                except Exception:
                    continue
        return False
