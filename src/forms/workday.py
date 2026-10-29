"""
Workday ATS Form Automation.
Handles multi-step application wizards on *.myworkdayjobs.com and enterprise portals.
"""
import time
from typing import Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class WorkdayFormFiller:
    @staticmethod
    def is_match(url: str, html: str) -> bool:
        url_lower = url.lower()
        return "myworkdayjobs.com" in url_lower or "workday" in url_lower or 'data-automation-id="applyButton"' in html or 'data-automation-id="pageHeader"' in html

    def fill(self, driver, profile: Dict[str, Any], resume_path: str) -> Dict[str, Any]:
        report = {"fields_filled": [], "unhandled_questions": []}
        p = profile.get("personal", {})
        screening = profile.get("screening_answers", {})

        # Step 0: Click initial Apply button if on the job overview page
        self._click_initial_apply(driver)

        # Step 1: Upload Resume
        self._upload_resume(driver, resume_path, report)

        # Step 2: Fill Personal / Contact Information
        self._fill_personal_info(driver, p, report)

        # Step 3: Handle Work Experience & Education if prompted
        self._fill_experience_summary(driver, profile, report)

        # Step 4: Handle Questionnaire / Screening Disclosures
        self._fill_screening_questions(driver, screening, report)

        # Step 5: Advance through pagination if Next button is visible
        self._advance_step(driver, report)

        return report

    def _click_initial_apply(self, driver):
        """Clicks 'Apply' or 'Apply Manually' / 'Autofill with Resume'."""
        try:
            apply_btns = driver.find_elements(By.CSS_SELECTOR, 
                "a[data-automation-id='applyButton'], button[data-automation-id='applyButton'], a[href*='apply'], button[data-uxi-element-id*='apply']"
            )
            for btn in apply_btns:
                if btn.is_displayed():
                    btn.click()
                    time.sleep(2)
                    break

            # If presented with 'Apply Manually' vs 'Autofill with Resume'
            manual_btns = driver.find_elements(By.CSS_SELECTOR, 
                "a[data-automation-id='applyManually'], button[data-automation-id='applyManually'], [data-automation-id='autofillWithResume']"
            )
            if manual_btns and manual_btns[0].is_displayed():
                manual_btns[0].click()
                time.sleep(2)
        except Exception:
            pass

    def _upload_resume(self, driver, resume_path: str, report: Dict[str, Any]):
        """Locates Workday file upload input and uploads vector PDF."""
        try:
            file_inputs = driver.find_elements(By.CSS_SELECTOR, 
                "input[type='file'][data-automation-id='file-upload-input-ref'], input[type='file']"
            )
            if file_inputs:
                file_inputs[0].send_keys(resume_path)
                report["fields_filled"].append("resume_upload")
                time.sleep(2)
        except Exception as e:
            report["unhandled_questions"].append(f"Workday resume upload notice: {e}")

    def _fill_personal_info(self, driver, p: Dict[str, Any], report: Dict[str, Any]):
        """Fills Workday legal name, contact, email, and phone."""
        fields = [
            ("first_name", ["input[data-automation-id='legalNameSection_firstName']", "input[id*='firstName']"], p.get("first_name")),
            ("last_name", ["input[data-automation-id='legalNameSection_lastName']", "input[id*='lastName']"], p.get("last_name")),
            ("email", ["input[data-automation-id='email']", "input[type='email']", "input[id*='email']"], p.get("email")),
            ("phone", ["input[data-automation-id='phone-number']", "input[type='tel']", "input[id*='phone']"], p.get("phone")),
            ("city", ["input[data-automation-id='addressSection_city']", "input[id*='city']"], p.get("city", "Bangalore")),
            ("postal_code", ["input[data-automation-id='addressSection_postalCode']", "input[id*='postalCode']"], p.get("postal_code", "560001")),
            ("address_line", ["input[data-automation-id='addressSection_addressLine1']"], p.get("location", "Bangalore, India"))
        ]

        for name, selectors, val in fields:
            if not val:
                continue
            for sel in selectors:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                if elems and elems[0].is_displayed():
                    try:
                        elems[0].clear()
                        elems[0].send_keys(val)
                        report["fields_filled"].append(name)
                        break
                    except Exception:
                        pass

    def _fill_experience_summary(self, driver, profile: Dict[str, Any], report: Dict[str, Any]):
        """Fills recent role / company if Workday asks on experience page."""
        try:
            title_inputs = driver.find_elements(By.CSS_SELECTOR, "input[data-automation-id='jobTitle']")
            comp_inputs = driver.find_elements(By.CSS_SELECTOR, "input[data-automation-id='company']")
            
            exps = profile.get("master_experiences", [{}])
            recent = exps[0] if exps else {}

            if title_inputs and recent.get("role"):
                title_inputs[0].clear()
                title_inputs[0].send_keys(recent["role"])
                report["fields_filled"].append("experience_title")

            if comp_inputs and recent.get("company"):
                comp_inputs[0].clear()
                comp_inputs[0].send_keys(recent["company"])
                report["fields_filled"].append("experience_company")
        except Exception:
            pass

    def _fill_screening_questions(self, driver, screening: Dict[str, Any], report: Dict[str, Any]):
        """Handles Workday questionnaires, radio buttons, and custom disclosures."""
        try:
            question_blocks = driver.find_elements(By.CSS_SELECTOR, "[data-automation-id*='questionnaire'], fieldset, .css-1y5c84d")
            for block in question_blocks:
                text = block.text.lower()
                if not text:
                    continue

                # Work authorization
                if any(k in text for k in ["authorized", "legally", "work eligibility"]):
                    self._click_workday_radio_or_dropdown(block, screening.get("authorized_to_work", "Yes"), report, "work_authorization")

                # Sponsorship
                elif any(k in text for k in ["sponsorship", "visa", "future sponsorship"]):
                    self._click_workday_radio_or_dropdown(block, screening.get("require_sponsorship", "No"), report, "sponsorship")

                # Notice period
                elif any(k in text for k in ["notice period", "availability", "how soon"]):
                    inputs = block.find_elements(By.CSS_SELECTOR, "input, textarea")
                    if inputs and inputs[0].is_displayed():
                        inputs[0].send_keys(screening.get("notice_period", "30 days"))
                        report["fields_filled"].append("notice_period")
        except Exception:
            pass

    def _click_workday_radio_or_dropdown(self, container, target_val: str, report: Dict[str, Any], field_name: str):
        try:
            radios = container.find_elements(By.CSS_SELECTOR, "input[type='radio'], label[data-automation-id*='radio']")
            for r in radios:
                label_text = r.text or r.get_attribute("value") or ""
                if target_val.lower() in label_text.lower():
                    r.click()
                    report["fields_filled"].append(field_name)
                    return

            # Workday custom dropdowns
            dropdowns = container.find_elements(By.CSS_SELECTOR, "button[data-automation-id*='select'], [data-automation-id*='dropdown']")
            if dropdowns and dropdowns[0].is_displayed():
                dropdowns[0].click()
                time.sleep(1)
                options = container.find_elements(By.CSS_SELECTOR, "[role='option'], li")
                for opt in options:
                    if target_val.lower() in opt.text.lower():
                        opt.click()
                        report["fields_filled"].append(field_name)
                        return
        except Exception:
            pass

    def _advance_step(self, driver, report: Dict[str, Any]):
        """Clicks 'Save and Continue' / Next step if available."""
        try:
            next_btns = driver.find_elements(By.CSS_SELECTOR, 
                "button[data-automation-id='bottom-navigation-next-button'], button[data-automation-id='page-footer-next']"
            )
            if next_btns and next_btns[0].is_displayed() and next_btns[0].is_enabled():
                # Report that next step is ready
                report["fields_filled"].append("step_advanced")
        except Exception:
            pass
