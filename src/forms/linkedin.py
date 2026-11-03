"""
LinkedIn Job Application Automation.
Handles both LinkedIn Easy Apply multi-step modal dialogs and external career portal redirects
(e.g., Workday, Greenhouse, Lever, Ashby, and company career portals).
"""

import time
import re
from typing import Dict, Any, List
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementClickInterceptedException,
    TimeoutException,
)

from .workday import WorkdayFormFiller
from .greenhouse import GreenhouseFormFiller
from .lever import LeverFormFiller
from .ashby import AshbyFormFiller
from .generic import GenericFormFiller


class LinkedInFormFiller:
    @staticmethod
    def is_match(url: str, html: str) -> bool:
        url_lower = url.lower()
        return (
            "linkedin.com/jobs" in url_lower
            or "linkedin.com/job" in url_lower
            or "jobs-easy-apply" in html
        )

    def fill(self, driver, profile: Dict[str, Any], resume_path: str) -> Dict[str, Any]:
        """
        Main entry point for applying to a LinkedIn job posting.
        Detects if the posting uses Easy Apply or redirects to an external ATS.
        """
        report: Dict[str, Any] = {"fields_filled": [], "unhandled_questions": []}
        time.sleep(2)

        # ── 1. Check for Easy Apply ───────────────────────────────────────────
        easy_apply_btn = self._find_easy_apply_button(driver)
        if easy_apply_btn:
            print("[*] LinkedIn Easy Apply detected! Launching in-page application wizard...")
            return self._handle_easy_apply(driver, easy_apply_btn, profile, resume_path, report)

        # ── 2. Check for External Apply ───────────────────────────────────────
        ext_btn = self._find_external_apply_button(driver)
        if ext_btn:
            print("[*] LinkedIn External Apply detected! Following redirect to company career page...")
            return self._handle_external_apply(driver, ext_btn, profile, resume_path, report)

        report["unhandled_questions"].append(
            "Neither Easy Apply nor External Apply button found on page."
        )
        return report

    # ── Easy Apply Flow ───────────────────────────────────────────────────────

    def _find_easy_apply_button(self, driver):
        selectors = [
            "button.jobs-apply-button",
            "button[data-job-id]",
            "button[aria-label*='Easy Apply' i]",
            "button.jobs-apply-button--top-card",
            ".jobs-s-apply button",
            "button[data-control-name='jobdetails_topcard_inapply']",
        ]
        for sel in selectors:
            for btn in driver.find_elements(By.CSS_SELECTOR, sel):
                try:
                    text = (btn.text or btn.get_attribute("aria-label") or "").lower()
                    if "easy apply" in text and btn.is_displayed():
                        return btn
                except Exception:
                    continue
        return None

    def _find_external_apply_button(self, driver):
        selectors = [
            "button.apply-button",
            "a.apply-button",
            "button[aria-label*='Apply to' i]",
            "a[aria-label*='Apply to' i]",
            "button.jobs-apply-button",
            "a[href*='externalApply']",
            "a[href*='applyUrl']",
            ".jobs-apply-button",
        ]
        for sel in selectors:
            for btn in driver.find_elements(By.CSS_SELECTOR, sel):
                try:
                    if btn.is_displayed():
                        return btn
                except Exception:
                    continue
        return None

    def _handle_easy_apply(
        self, driver, apply_btn, profile: Dict[str, Any], resume_path: str, report: Dict[str, Any]
    ) -> Dict[str, Any]:
        p = profile.get("personal", {})
        screening = profile.get("screening_answers", {})
        years_exp = str(profile.get("total_experience_years", 6))

        try:
            apply_btn.click()
            time.sleep(2)
        except Exception as e:
            try:
                driver.execute_script("arguments[0].click();", apply_btn)
                time.sleep(2)
            except Exception as e2:
                report["unhandled_questions"].append(f"Failed to click Easy Apply: {e2}")
                return report

        # Loop through modal steps (up to 8 steps)
        max_steps = 8
        current_step = 0

        while current_step < max_steps:
            current_step += 1
            time.sleep(1.5)

            modal = self._get_modal(driver)
            if not modal:
                break

            # Fill inputs in current step
            self._fill_modal_inputs(modal, p, screening, years_exp, report)

            # Upload resume if file input is present
            self._upload_resume_in_modal(modal, resume_path, report)

            # Check if this is the final Review / Submit step
            submit_btn = self._find_modal_button(
                modal,
                [
                    "button[aria-label*='Submit application' i]",
                    "button[data-control-name='submit_un恢']",
                    "button.artdeco-button--primary[aria-label*='Submit' i]",
                ],
            )
            if submit_btn:
                report["fields_filled"].append("easy_apply_review_ready")
                print("[+] LinkedIn Easy Apply form fully pre-filled and reached Review/Submit step!")
                break

            # Try clicking Next or Review
            next_btn = self._find_modal_button(
                modal,
                [
                    "button[aria-label*='Continue to next step' i]",
                    "button[data-easy-apply-next-button]",
                    "button[aria-label*='Review your application' i]",
                    "button.artdeco-button--primary",
                ],
            )
            if next_btn and next_btn.is_enabled():
                try:
                    next_btn.click()
                    report["fields_filled"].append(f"easy_apply_step_{current_step}")
                except Exception:
                    driver.execute_script("arguments[0].click();", next_btn)
                    report["fields_filled"].append(f"easy_apply_step_{current_step}")
            else:
                break

        return report

    def _get_modal(self, driver):
        selectors = [
            "div.jobs-easy-apply-modal",
            "div[data-test-modal]",
            "div[role='dialog']",
            ".artdeco-modal",
        ]
        for sel in selectors:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in elems:
                if el.is_displayed():
                    return el
        return None

    def _find_modal_button(self, modal, selectors: List[str]):
        for sel in selectors:
            for btn in modal.find_elements(By.CSS_SELECTOR, sel):
                try:
                    if btn.is_displayed():
                        return btn
                except Exception:
                    continue
        return None

    def _fill_modal_inputs(
        self, modal, p: Dict[str, Any], screening: Dict[str, Any], years_exp: str, report: Dict[str, Any]
    ):
        # 1. Text / Tel inputs
        inputs = modal.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='tel'], input[type='number']")
        for inp in inputs:
            try:
                if not inp.is_displayed():
                    continue
                val = inp.get_attribute("value") or ""
                label_text = self._get_label_text(inp).lower()

                if ("phone" in label_text or "mobile" in label_text) and not val:
                    inp.clear()
                    inp.send_keys(p.get("phone", "+91-7017088496"))
                    report["fields_filled"].append("phone")

                elif ("experience" in label_text or "year" in label_text) and not val:
                    inp.clear()
                    inp.send_keys(years_exp)
                    report["fields_filled"].append("experience_years")

                elif ("notice" in label_text or "day" in label_text) and not val:
                    inp.clear()
                    inp.send_keys(screening.get("notice_period", "15 days"))
                    report["fields_filled"].append("notice_period")

                elif ("ctc" in label_text or "salary" in label_text or "compensation" in label_text) and not val:
                    inp.clear()
                    inp.send_keys(screening.get("expected_ctc", "35 LPA"))
                    report["fields_filled"].append("expected_salary")

                elif ("city" in label_text or "location" in label_text) and not val:
                    inp.clear()
                    inp.send_keys(p.get("location", "Bangalore, India"))
                    report["fields_filled"].append("city")

            except Exception:
                continue

        # 2. Radio buttons (Work authorization, relocation, sponsorship)
        fieldsets = modal.find_elements(By.CSS_SELECTOR, "fieldset")
        for fs in fieldsets:
            try:
                fs_text = fs.text.lower()
                target_answer = "yes"
                if "sponsorship" in fs_text or "visa" in fs_text:
                    target_answer = screening.get("require_sponsorship", "No").lower()
                elif "authorized" in fs_text or "legally" in fs_text:
                    target_answer = screening.get("authorized_to_work", "Yes").lower()
                elif "commute" in fs_text or "relocate" in fs_text:
                    target_answer = "yes"

                radios = fs.find_elements(By.CSS_SELECTOR, "input[type='radio']")
                for r in radios:
                    parent_text = r.find_element(By.XPATH, "..").text.lower()
                    if target_answer in parent_text:
                        if not r.is_selected():
                            r.click()
                        report["fields_filled"].append(f"radio_{target_answer}")
                        break
            except Exception:
                continue

    def _upload_resume_in_modal(self, modal, resume_path: str, report: Dict[str, Any]):
        file_inputs = modal.find_elements(By.CSS_SELECTOR, "input[type='file']")
        for finp in file_inputs:
            try:
                finp.send_keys(resume_path)
                report["fields_filled"].append("resume_upload")
                time.sleep(1)
                break
            except Exception:
                continue

    def _get_label_text(self, element) -> str:
        try:
            elem_id = element.get_attribute("id")
            if elem_id:
                labels = element.find_elements(By.XPATH, f"//label[@for='{elem_id}']")
                if labels:
                    return labels[0].text
            parent = element.find_element(By.XPATH, "..")
            return parent.text
        except Exception:
            return ""

    # ── External Apply Redirect Flow ──────────────────────────────────────────

    def _handle_external_apply(
        self, driver, apply_btn, profile: Dict[str, Any], resume_path: str, report: Dict[str, Any]
    ) -> Dict[str, Any]:
        initial_handles = list(driver.window_handles)

        try:
            apply_btn.click()
            time.sleep(3)
        except Exception:
            driver.execute_script("arguments[0].click();", apply_btn)
            time.sleep(3)

        new_handles = [h for h in driver.window_handles if h not in initial_handles]
        if new_handles:
            # Switched to external tab
            target_tab = new_handles[-1]
            driver.switch_to.window(target_tab)
            time.sleep(3)
            current_url = driver.current_url
            page_source = driver.page_source
            print(f"[*] Redirected to external portal: {current_url[:90]}")

            # Delegate to specialized ATS filler
            if WorkdayFormFiller.is_match(current_url, page_source):
                print("[*] Detected Workday on redirected portal")
                sub_report = WorkdayFormFiller().fill(driver, profile, resume_path)
            elif GreenhouseFormFiller.is_match(current_url, page_source):
                print("[*] Detected Greenhouse on redirected portal")
                sub_report = GreenhouseFormFiller().fill(driver, profile, resume_path)
            elif LeverFormFiller.is_match(current_url, page_source):
                print("[*] Detected Lever on redirected portal")
                sub_report = LeverFormFiller().fill(driver, profile, resume_path)
            elif AshbyFormFiller.is_match(current_url, page_source):
                print("[*] Detected Ashby on redirected portal")
                sub_report = AshbyFormFiller().fill(driver, profile, resume_path)
            else:
                print("[*] Detected Generic/Company Portal on redirected page")
                sub_report = GenericFormFiller().fill(driver, profile, resume_path)

            report["fields_filled"].extend(sub_report.get("fields_filled", []))
            report["unhandled_questions"].extend(sub_report.get("unhandled_questions", []))
        else:
            report["fields_filled"].append("external_apply_clicked")

        return report
