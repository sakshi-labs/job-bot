"""
Generic Heuristic Form Filler.
Uses regex heuristics on labels, placeholders, aria-labels, and input names
to fill out arbitrary career portal forms.
"""
import re
from typing import Dict, Any
from selenium.webdriver.common.by import By

class GenericFormFiller:
    @staticmethod
    def is_match(url: str, html: str) -> bool:
        return True  # Fallback for any ATS

    def fill(self, driver, profile: Dict[str, Any], resume_path: str) -> Dict[str, Any]:
        report = {"fields_filled": [], "unhandled_questions": []}
        p = profile.get("personal", {})
        screening = profile.get("screening_answers", {})

        inputs = driver.find_elements(By.TAG_NAME, "input")
        
        for inp in inputs:
            try:
                if not inp.is_displayed():
                    # Check if it's a file input (often hidden)
                    if inp.get_attribute("type") == "file" and "resume_upload" not in report["fields_filled"]:
                        inp.send_keys(resume_path)
                        report["fields_filled"].append("resume_upload")
                    continue

                inp_type = (inp.get_attribute("type") or "text").lower()
                name_attr = (inp.get_attribute("name") or "").lower()
                id_attr = (inp.get_attribute("id") or "").lower()
                placeholder = (inp.get_attribute("placeholder") or "").lower()
                aria_label = (inp.get_attribute("aria-label") or "").lower()
                
                identifier = f"{name_attr} {id_attr} {placeholder} {aria_label}"

                # Resume File Upload
                if inp_type == "file" and "resume_upload" not in report["fields_filled"]:
                    inp.send_keys(resume_path)
                    report["fields_filled"].append("resume_upload")
                    continue

                # Email
                if inp_type == "email" or "email" in identifier:
                    if p.get("email") and "email" not in report["fields_filled"]:
                        inp.clear()
                        inp.send_keys(p["email"])
                        report["fields_filled"].append("email")
                        continue

                # Phone
                if inp_type == "tel" or any(k in identifier for k in ["phone", "mobile", "telephone"]):
                    if p.get("phone") and "phone" not in report["fields_filled"]:
                        inp.clear()
                        inp.send_keys(p["phone"])
                        report["fields_filled"].append("phone")
                        continue

                # First Name
                if any(k in identifier for k in ["first_name", "firstname", "first name", "given name"]):
                    if p.get("first_name") and "first_name" not in report["fields_filled"]:
                        inp.clear()
                        inp.send_keys(p["first_name"])
                        report["fields_filled"].append("first_name")
                        continue

                # Last Name
                if any(k in identifier for k in ["last_name", "lastname", "last name", "surname", "family name"]):
                    if p.get("last_name") and "last_name" not in report["fields_filled"]:
                        inp.clear()
                        inp.send_keys(p["last_name"])
                        report["fields_filled"].append("last_name")
                        continue

                # Full Name
                if "name" in identifier and "first" not in identifier and "last" not in identifier:
                    if p.get("full_name") and "full_name" not in report["fields_filled"]:
                        inp.clear()
                        inp.send_keys(p["full_name"])
                        report["fields_filled"].append("full_name")
                        continue

                # LinkedIn
                if "linkedin" in identifier:
                    if p.get("linkedin") and "linkedin" not in report["fields_filled"]:
                        inp.clear()
                        inp.send_keys(p["linkedin"])
                        report["fields_filled"].append("linkedin")
                        continue

                # GitHub
                if "github" in identifier:
                    if p.get("github") and "github" not in report["fields_filled"]:
                        inp.clear()
                        inp.send_keys(p["github"])
                        report["fields_filled"].append("github")
                        continue

                # Website / Portfolio
                if any(k in identifier for k in ["website", "portfolio", "blog"]):
                    if p.get("portfolio") and "portfolio" not in report["fields_filled"]:
                        inp.clear()
                        inp.send_keys(p["portfolio"])
                        report["fields_filled"].append("portfolio")
                        continue

            except Exception:
                continue

        return report
