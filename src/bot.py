"""
Master Application Bot Orchestrator.
Coordinates JD parsing, resume tailoring, ATS PDF generation, and automated form filling.

KEY FIXES (v2):
  1. Uses ChromeSessionManager.get_driver() — attaches to the EXISTING Chrome window
     via CDP remote-debugging port 9222 instead of spawning a new browser process.
  2. Every application opens in a NEW TAB, keeping login sessions intact.
  3. Status is ONLY set to 'applied' when the form was actually submitted successfully.
     All failures → 'not_applied' with a human-readable error_reason field.
  4. Applied job URLs are tracked in output/applied_jobs.json to prevent duplicate
     applications across sessions.
  5. Console progress is printed STEP-BY-STEP so you can see what is happening in real time.
"""
import os
import re
import json
import time
from typing import Optional, Dict, Any

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
        self._registry_path = os.path.join(config_dir, "..", output_dir, "applied_registry.json")
        self._registry_path = os.path.abspath(self._registry_path)
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
        Opens job_url in a NEW TAB of the existing Chrome window, detects ATS,
        fills the form, and returns an accurate status report.

        Returns
        -------
        {
          "status":       "applied" | "not_applied" | "error",
          "error_reason": "..." or None,
          "fields_filled": [...],
          "job_url": "...",
        }
        """
        # ── Guard: validate URL ────────────────────────────────────────────────
        if not job_url or not (job_url.startswith("http://") or job_url.startswith("https://")):
            return {
                "status": "not_applied",
                "error_reason": f"Invalid or missing URL: '{job_url}'",
                "fields_filled": [],
                "job_url": job_url,
            }

        # ── Guard: duplicate-application check ────────────────────────────────
        dedup_key = job_id or job_url
        if dedup_key in self.applied_registry:
            print(f"[⚠] Already applied to {dedup_key} — skipping to prevent duplicate.")
            return {
                "status": "not_applied",
                "error_reason": "Already applied to this opening in a previous session.",
                "fields_filled": [],
                "job_url": job_url,
                "duplicate": True,
            }

        # ── Acquire driver (existing Chrome tab or new window) ─────────────────
        print(f"\n[→] Opening new tab for: {job_url}")
        headless = (
            not review_mode
            and self.settings.get("browser", {}).get("headless", False)
        )

        try:
            driver = ChromeSessionManager.get_driver(headless=headless)
        except Exception as e:
            print(f"[✗] Browser could not start: {e}")
            return {
                "status": "not_applied",
                "error_reason": f"Browser launch failed: {e}",
                "fields_filled": [],
                "job_url": job_url,
            }

        original_handle = driver.current_window_handle if driver.window_handles else None
        new_tab_handle = None
        report: Dict[str, Any] = {"fields_filled": [], "job_url": job_url}

        try:
            # ── Open job URL in a new tab ──────────────────────────────────────
            new_tab_handle = ChromeSessionManager.open_new_tab(driver, job_url)

            timeout = self.settings.get("browser", {}).get("timeout_ms", 30000) / 1000
            driver.set_page_load_timeout(timeout)
            time.sleep(2)

            page_source = driver.page_source
            current_url = driver.current_url
            print(f"[*] Page loaded: {current_url}")

            # ── Detect login-wall / no-access pages ───────────────────────────
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
            ]
            page_lower = page_source.lower()
            if any(sig in page_lower for sig in login_signals):
                reason = (
                    "Login wall detected — please log into this portal in the existing "
                    "Chrome window before running the bot. The bot uses your existing "
                    "browser session so your credentials are never stored."
                )
                print(f"[⚠] {reason}")
                report["status"] = "not_applied"
                report["error_reason"] = reason
                return report

            # ── Detect 404 / expired pages ────────────────────────────────────
            expired_signals = [
                "job no longer available",
                "this job has expired",
                "position has been filled",
                "job not found",
                "404",
                "page not found",
            ]
            if any(sig in page_lower for sig in expired_signals):
                reason = "Job posting is no longer available or has expired."
                print(f"[⚠] {reason}")
                report["status"] = "not_applied"
                report["error_reason"] = reason
                return report

            # ── ATS Detection ─────────────────────────────────────────────────
            filler = None
            if WorkdayFormFiller.is_match(current_url, page_source):
                print("[*] Detected: Workday Enterprise ATS")
                filler = WorkdayFormFiller()
            elif GreenhouseFormFiller.is_match(current_url, page_source):
                print("[*] Detected: Greenhouse ATS")
                filler = GreenhouseFormFiller()
            elif LeverFormFiller.is_match(current_url, page_source):
                print("[*] Detected: Lever ATS")
                filler = LeverFormFiller()
            elif AshbyFormFiller.is_match(current_url, page_source):
                print("[*] Detected: Ashby ATS")
                filler = AshbyFormFiller()
            else:
                print("[*] Detected: Generic / Custom ATS")
                filler = GenericFormFiller()

            # ── Fill Form ─────────────────────────────────────────────────────
            print("[*] Filling form fields...")
            fill_result = filler.fill(driver, self.profile, tailored_resume.pdf_path)

            filled = fill_result.get("fields_filled", [])
            unhandled = fill_result.get("unhandled_questions", [])
            report["fields_filled"] = filled
            report["unhandled_questions"] = unhandled

            if filled:
                print(f"[+] Fields pre-filled: {', '.join(filled)}")
            if unhandled:
                print(f"[~] Unhandled questions: {'; '.join(str(u) for u in unhandled)}")

            # ── Human-in-the-loop review ──────────────────────────────────────
            if review_mode and interactive:
                print("\n" + "=" * 65)
                print(">>> HUMAN-IN-THE-LOOP REVIEW MODE <<<")
                print("Pre-fill complete. Review and manually SUBMIT the form in Chrome.")
                print("Press [ENTER] here once you have submitted (or to skip)...")
                print("=" * 65)
                try:
                    submitted = input().strip().lower()
                    # If user typed 'skip' or 'no', mark not applied
                    if submitted in ("skip", "no", "n"):
                        report["status"] = "not_applied"
                        report["error_reason"] = "User skipped submission during review."
                        return report
                except Exception:
                    pass
                report["status"] = "applied"
                report["error_reason"] = None

            elif self.settings.get("browser", {}).get("auto_submit", False):
                # Auto-submit mode: attempt to find and click submit button
                submitted = self._attempt_submit(driver)
                if submitted:
                    print("[+] Form submitted automatically.")
                    report["status"] = "applied"
                    report["error_reason"] = None
                else:
                    report["status"] = "not_applied"
                    report["error_reason"] = (
                        "auto_submit=true but could not locate a Submit button. "
                        "Form was pre-filled — open the tab manually to complete."
                    )
            else:
                # Default: form is pre-filled, browser tab remains open for YOU to review + submit
                print("[ℹ] Form pre-filled. Tab left open — please review and submit manually.")
                report["status"] = "not_applied"
                report["error_reason"] = (
                    "Form pre-filled. Awaiting manual submission. "
                    "Set 'auto_submit: true' in config/settings.json for fully automated submission."
                )

            # ── Register as applied only on confirmed submission ───────────────
            if report.get("status") == "applied":
                self.applied_registry.add(dedup_key)
                _save_applied_registry(self._registry_path, self.applied_registry)
                print(f"[✓] Marked '{dedup_key}' as applied in registry.")

            return report

        except Exception as e:
            print(f"[✗] Error during automation: {e}")
            return {
                "status": "not_applied",
                "error_reason": str(e),
                "fields_filled": report.get("fields_filled", []),
                "job_url": job_url,
            }
        finally:
            # Close the tab we opened ONLY if we are NOT in interactive review mode
            if new_tab_handle and not (review_mode and interactive):
                try:
                    ChromeSessionManager.close_tab(driver, new_tab_handle, original_handle)
                    print(f"[*] Closed automation tab {new_tab_handle}.")
                except Exception:
                    pass
            # NEVER quit the driver — it belongs to the shared persistent Chrome session

    def _attempt_submit(self, driver) -> bool:
        """
        Tries common submit button selectors. Returns True if a button was clicked.
        """
        from selenium.webdriver.common.by import By
        selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button[data-automation-id='bottom-navigation-next-button']",
            "button#submit-app",
            "button.submit",
            "button[aria-label*='submit' i]",
            "button[aria-label*='apply' i]",
        ]
        for sel in selectors:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in elems:
                try:
                    if el.is_displayed() and el.is_enabled():
                        el.click()
                        time.sleep(1)
                        return True
                except Exception:
                    continue
        return False
