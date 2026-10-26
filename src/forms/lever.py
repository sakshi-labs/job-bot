"""
Lever ATS Form Automation.
"""
from typing import Dict, Any
from selenium.webdriver.common.by import By

class LeverFormFiller:
    @staticmethod
    def is_match(url: str, html: str) -> bool:
        return "lever.co" in url or "posting-headline" in html

    def fill(self, driver, profile: Dict[str, Any], resume_path: str) -> Dict[str, Any]:
        report = {"fields_filled": [], "unhandled_questions": []}
        p = profile.get("personal", {})
        screening = profile.get("screening_answers", {})

        # Lever form uses name attributes: name, email, phone, org, urls[LinkedIn], urls[GitHub], urls[Portfolio]
        fields = [
            ("full_name", "input[name='name']", p.get("full_name")),
            ("email", "input[name='email']", p.get("email")),
            ("phone", "input[name='phone']", p.get("phone")),
            ("org", "input[name='org']", profile.get("master_experiences", [{}])[0].get("company", "")),
            ("linkedin", "input[name='urls[LinkedIn]']", p.get("linkedin")),
            ("github", "input[name='urls[GitHub]']", p.get("github")),
            ("portfolio", "input[name='urls[Portfolio]'], input[name='urls[Other]']", p.get("portfolio"))
        ]

        for field_name, selector, val in fields:
            if not val:
                continue
            elems = driver.find_elements(By.CSS_SELECTOR, selector)
            if elems:
                try:
                    elems[0].clear()
                    elems[0].send_keys(val)
                    report["fields_filled"].append(field_name)
                except Exception:
                    pass

        # Resume file upload
        file_inputs = driver.find_elements(By.CSS_SELECTOR, "input[name='resume'][type='file'], input[type='file']")
        if file_inputs:
            try:
                file_inputs[0].send_keys(resume_path)
                report["fields_filled"].append("resume_upload")
            except Exception as e:
                report["unhandled_questions"].append(f"Resume upload failed: {e}")

        # Screening questions / additional cards
        cards = driver.find_elements(By.CSS_SELECTOR, ".application-question, .custom-question")
        for card in cards:
            text = card.text.lower()
            if any(k in text for k in ["sponsorship", "visa"]):
                self._fill_card_input(card, screening.get("require_sponsorship", "No"), report, "sponsorship")
            elif any(k in text for k in ["authorized", "legally"]):
                self._fill_card_input(card, screening.get("authorized_to_work", "Yes"), report, "work_authorization")

        return report

    def _fill_card_input(self, card, target_val: str, report: Dict, name: str):
        radios = card.find_elements(By.CSS_SELECTOR, "input[type='radio']")
        for r in radios:
            parent = r.find_element(By.XPATH, "..").text.lower()
            if target_val.lower() in parent:
                try:
                    r.click()
                    report["fields_filled"].append(name)
                    return
                except Exception:
                    pass
