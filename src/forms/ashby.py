"""
Ashby ATS Form Automation.
"""
from typing import Dict, Any
from selenium.webdriver.common.by import By

class AshbyFormFiller:
    @staticmethod
    def is_match(url: str, html: str) -> bool:
        return "ashbyhq.com" in url

    def fill(self, driver, profile: Dict[str, Any], resume_path: str) -> Dict[str, Any]:
        report = {"fields_filled": [], "unhandled_questions": []}
        p = profile.get("personal", {})

        # Ashby fields typically have test-ids or labeled inputs
        field_matchers = [
            ("name", ["input[name*='name']", "input[placeholder*='Name']"], p.get("full_name")),
            ("email", ["input[type='email']", "input[name*='email']"], p.get("email")),
            ("phone", ["input[type='tel']", "input[name*='phone']"], p.get("phone")),
            ("linkedin", ["input[name*='linkedin']", "input[placeholder*='linkedin']"], p.get("linkedin")),
            ("github", ["input[name*='github']", "input[placeholder*='github']"], p.get("github"))
        ]

        for field_name, selectors, val in field_matchers:
            if not val:
                continue
            for sel in selectors:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                if elems:
                    try:
                        elems[0].clear()
                        elems[0].send_keys(val)
                        report["fields_filled"].append(field_name)
                        break
                    except Exception:
                        pass

        file_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
        if file_inputs:
            try:
                file_inputs[0].send_keys(resume_path)
                report["fields_filled"].append("resume_upload")
            except Exception as e:
                report["unhandled_questions"].append(f"Resume upload failed: {e}")

        return report
