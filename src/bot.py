"""
Master Application Bot Orchestrator.
Coordinates JD parsing, resume tailoring, ATS PDF generation, and automated form filling.
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
from .forms.greenhouse import GreenhouseFormFiller
from .forms.lever import LeverFormFiller
from .forms.ashby import AshbyFormFiller
from .forms.generic import GenericFormFiller

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

    def process_and_tailor(self, jd_input: str, is_url: bool = False, profile: Optional[Dict[str, Any]] = None, customizations: Optional[Dict[str, Any]] = None) -> TailoredResume:
        """Parses JD and generates a fully tailored resume PDF and HTML using active or customized profile."""
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
        print(f"[*] Analyzing requirements for '{jd.title}' at '{jd.company}' using profile: {active_prof.get('profile_name', 'default')}...")

        tailored = self.tailor.tailor(jd, profile=active_prof, customizations=customizations)
        print(f"[+] Tailoring complete! ATS Match Score: {tailored.ats_score}%")

        # Clean file slug
        safe_company = re.sub(r'[^a-zA-Z0-9]', '_', tailored.target_company.lower()).strip('_')
        safe_role = re.sub(r'[^a-zA-Z0-9]', '_', tailored.target_role.lower()).strip('_')
        out_dir = self.settings.get("output_dir", "output")
        os.makedirs(out_dir, exist_ok=True)

        pdf_path = os.path.abspath(os.path.join(out_dir, f"resume_{safe_company}_{safe_role}.pdf"))
        html_path = os.path.abspath(os.path.join(out_dir, f"resume_{safe_company}_{safe_role}.html"))

        self.pdf_generator.generate(tailored, pdf_path)
        generate_html_resume(tailored, html_path)

        tailored.pdf_path = pdf_path
        tailored.html_path = html_path
        return tailored

    def apply_to_job(self, job_url: str, tailored_resume: TailoredResume, review_mode: bool = False, interactive: bool = False) -> Dict[str, Any]:
        """Automates browser navigation, ATS detection, form filling, and resume upload."""
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        if not job_url or not (job_url.startswith("http://") or job_url.startswith("https://")):
            return {"status": "error", "message": f"Invalid URL: '{job_url}'", "fields_filled": []}

        print(f"\n[*] Launching browser for: {job_url}")
        options = Options()
        # In web background mode or when headless is set
        if not review_mode and self.settings.get("browser", {}).get("headless", False):
            options.add_argument("--headless=new")
        
        # Anti-detection parameters
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--start-maximized")
        options.add_argument(f"user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

        try:
            driver = webdriver.Chrome(options=options)
        except Exception as e:
            print(f"[!] Could not launch Chrome: {e}")
            return {"status": "error", "message": f"Browser launch failed: {e}", "fields_filled": []}

        try:
            driver.set_page_load_timeout(15)
            try:
                driver.get(job_url)
            except Exception as load_err:
                print(f"[!] Page load warning: {load_err}")
            time.sleep(2)

            page_source = driver.page_source
            current_url = driver.current_url

            # Select appropriate ATS filler
            filler = None
            if GreenhouseFormFiller.is_match(current_url, page_source):
                print("[*] Detected Greenhouse ATS portal.")
                filler = GreenhouseFormFiller()
            elif LeverFormFiller.is_match(current_url, page_source):
                print("[*] Detected Lever ATS portal.")
                filler = LeverFormFiller()
            elif AshbyFormFiller.is_match(current_url, page_source):
                print("[*] Detected Ashby ATS portal.")
                filler = AshbyFormFiller()
            else:
                print("[*] Detected Custom / Generic ATS portal. Using Heuristic Form Filler.")
                filler = GenericFormFiller()

            report = filler.fill(driver, self.profile, tailored_resume.pdf_path)
            print(f"[+] Pre-filled fields: {', '.join(report.get('fields_filled', []))}")

            # Only pause for terminal stdin if explicitly in CLI interactive mode!
            if review_mode and interactive:
                print("\n" + "="*65)
                print(">>> HUMAN-IN-THE-LOOP REVIEW MODE <<<")
                print("The bot has pre-filled your details and uploaded the tailored PDF.")
                print("Please review the form in the browser window and press [ENTER] when done...")
                print("="*65)
                try:
                    input()
                except Exception:
                    pass
            else:
                time.sleep(2)

            report["status"] = "success"
            return report
        except Exception as e:
            print(f"[!] Error during form automation: {e}")
            return {"status": "error", "message": str(e), "fields_filled": []}
        finally:
            # If not keeping browser open for interactive inspection
            if not (review_mode and interactive):
                try:
                    driver.quit()
                except Exception:
                    pass
