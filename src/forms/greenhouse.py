"""
Greenhouse ATS Form Automation.
"""
import time
from typing import Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class GreenhouseFormFiller:
    @staticmethod
    def is_match(url: str, html: str) -> bool:
        return "greenhouse.io" in url or "gh_jid" in url or 'id="application_form"' in html

    def fill(self, driver, profile: Dict[str, Any], resume_path: str) -> Dict[str, Any]:
        report = {"fields_filled": [], "unhandled_questions": []}
        wait = WebDriverWait(driver, 10)
        
        # Switch to Greenhouse iframe if embedded
        iframes = driver.find_elements(By.CSS_SELECTOR, "iframe#grnhse_iframe, iframe[src*='greenhouse']")
        if iframes:
            driver.switch_to.frame(iframes[0])

        p = profile.get("personal", {})
        screening = profile.get("screening_answers", {})

        # Standard Fields Mapping
        field_mappings = [
            ("first_name", ["#first_name", "input[id*='first_name']", "input[name*='first_name']"], p.get("first_name")),
            ("last_name", ["#last_name", "input[id*='last_name']", "input[name*='last_name']"], p.get("last_name")),
            ("email", ["#email", "input[id*='email']", "input[name*='email']"], p.get("email")),
            ("phone", ["#phone", "input[id*='phone']", "input[name*='phone']"], p.get("phone")),
            ("linkedin", ["input[id*='linkedin']", "input[autocomplete*='linkedin']", "input[name*='linkedin']"], p.get("linkedin")),
            ("website", ["input[id*='website']", "input[name*='website']", "input[id*='portfolio']"], p.get("portfolio"))
        ]

        for field_name, selectors, value in field_mappings:
            if not value:
                continue
            for sel in selectors:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                if elems and elems[0].is_displayed():
                    try:
                        elems[0].clear()
                        elems[0].send_keys(value)
                        report["fields_filled"].append(field_name)
                        break
                    except Exception:
                        pass

        # Resume File Upload
        file_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file'][id*='resume'], input[type='file']")
        if file_inputs:
            try:
                # Greenhouse sometimes hides the file input behind a button; send_keys directly to the input
                file_inputs[0].send_keys(resume_path)
                report["fields_filled"].append("resume_upload")
            except Exception as e:
                report["unhandled_questions"].append(f"Resume upload failed: {e}")

        # Screening Questions (Work authorization, sponsorship, etc.)
        self._fill_custom_questions(driver, screening, report)

        return report

    def _fill_custom_questions(self, driver, screening: Dict[str, Any], report: Dict[str, Any]):
        # Iterate over all custom question blocks
        questions = driver.find_elements(By.CSS_SELECTOR, ".field, [class*='question']")
        for q in questions:
            text = q.text.lower()
            if not text:
                continue

            # Work authorization
            if any(k in text for k in ["authorized", "legally", "work in"]):
                self._select_dropdown_or_radio(q, screening.get("authorized_to_work", "Yes"), report, "work_authorization")

            # Sponsorship
            elif any(k in text for k in ["sponsorship", "visa"]):
                self._select_dropdown_or_radio(q, screening.get("require_sponsorship", "No"), report, "sponsorship")

            # Notice Period
            elif any(k in text for k in ["notice period", "how soon", "start date"]):
                inputs = q.find_elements(By.CSS_SELECTOR, "input, select, textarea")
                if inputs:
                    try:
                        inputs[0].send_keys(screening.get("notice_period", "2 weeks"))
                        report["fields_filled"].append("notice_period")
                    except Exception:
                        pass

    def _select_dropdown_or_radio(self, container, target_val: str, report: Dict, name: str):
        # Radio buttons
        radios = container.find_elements(By.CSS_SELECTOR, "input[type='radio']")
        for r in radios:
            label = r.find_element(By.XPATH, "..").text.lower()
            if target_val.lower() in label:
                try:
                    r.click()
                    report["fields_filled"].append(name)
                    return
                except Exception:
                    pass
        # Select dropdowns
        selects = container.find_elements(By.TAG_NAME, "select")
        for s in selects:
            from selenium.webdriver.support.ui import Select
            sel = Select(s)
            for opt in sel.options:
                if target_val.lower() in opt.text.lower():
                    try:
                        sel.select_by_visible_text(opt.text)
                        report["fields_filled"].append(name)
                        return
                    except Exception:
                        pass
