"""
Autonomous Job Hunter Orchestrator.
Searches Hirist, Naukri, LinkedIn, and Top Company Career Pages for 40-50 LPA openings.
Uses ProfileSelector to match each job against the 5 candidate resumes in the bank,
provides per-job resume customization, single-click application, and background bulk-apply.
"""
import os
import json
import time
import threading
from typing import List, Dict, Any, Optional

from .jd_parser import JDParser
from .resume_bank import ResumeBank
from .profile_selector import ProfileSelector
from .scrapers.hirist import HiristScraper
from .scrapers.naukri import NaukriScraper
from .scrapers.linkedin import LinkedInScraper
from .scrapers.career_pages import CareerPagesScraper
from .scrapers.instahyre import InstahyreScraper
from .scrapers.wellfound import WellfoundScraper

class JobHunter:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.config_dir = os.path.join(root_dir, "config")
        self.resumes_dir = os.path.join(root_dir, "resumes")
        self.output_dir = os.path.join(root_dir, "output")
        self.queue_file = os.path.join(self.output_dir, "job_queue.json")
        os.makedirs(self.output_dir, exist_ok=True)

        settings_path = os.path.join(self.config_dir, "settings.json")
        self.settings = {}
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as f:
                self.settings = json.load(f)

        job_cfg = self.settings.get("job_search", {})
        self.min_ctc = job_cfg.get("min_ctc_lakhs", 30)
        self.max_ctc = job_cfg.get("max_ctc_lakhs", 40)

        # Initialize engines
        self.jd_parser = JDParser()
        self.resume_bank = ResumeBank(
            resumes_dir=self.resumes_dir,
            fallback_profile_path=os.path.join(self.config_dir, "master_profile.json")
        )
        self.selector = ProfileSelector(self.resume_bank)

        # Scrapers for 30-40L tech platforms & Workday
        self.instahyre = InstahyreScraper(self.min_ctc, self.max_ctc)
        self.wellfound = WellfoundScraper(self.min_ctc, self.max_ctc)
        self.hirist = HiristScraper(self.min_ctc, self.max_ctc)
        self.naukri = NaukriScraper(self.min_ctc, self.max_ctc)
        self.linkedin = LinkedInScraper(self.min_ctc, self.max_ctc)
        self.career_pages = CareerPagesScraper(self.min_ctc, self.max_ctc)

        # Background bulk-apply state tracking
        self.bulk_state = {
            "is_running": False,
            "total": 0,
            "completed": 0,
            "current_company": "",
            "results": [],
            "error": None
        }

    def hunt_jobs(self, query: str = "Backend", location: str = "Bangalore", limit_per_portal: int = 3) -> List[Dict[str, Any]]:
        """Discovers 40-50 LPA jobs across portals and matches each with the best resume profile."""
        print(f"\n[*] Starting Autonomous Job Hunt across portals for '{query}' in '{location}'...")
        print(f"[*] Target Compensation: {self.min_ctc} - {self.max_ctc} LPA")

        all_raw_jobs = []
        all_raw_jobs.extend(self.instahyre.search_jobs(query, location, limit=limit_per_portal))
        all_raw_jobs.extend(self.wellfound.search_jobs(query, location, limit=limit_per_portal))
        all_raw_jobs.extend(self.hirist.search_jobs(query, location, limit=limit_per_portal))
        all_raw_jobs.extend(self.naukri.search_jobs(query, location, limit=limit_per_portal))
        all_raw_jobs.extend(self.linkedin.search_jobs(f"Senior {query} Engineer", location, limit=limit_per_portal))
        all_raw_jobs.extend(self.career_pages.search_jobs(query, location, limit=limit_per_portal))

        processed_queue = self.load_queue()
        existing_urls = set(item.get("url") for item in processed_queue)

        new_items = []
        for raw in all_raw_jobs:
            url = raw.get("url", "")
            if url in existing_urls:
                continue

            jd_obj = self.jd_parser.parse_from_text(
                text=raw.get("description", "") + " " + raw.get("title", ""),
                title=raw.get("title", ""),
                company=raw.get("company", ""),
                url=url
            )

            # Evaluate against all 5 resumes in the bank!
            selection_res = self.selector.select_best_profile(jd_obj)
            winner = selection_res["winner"]
            w_profile = winner["profile"]

            # Generate initial tailored summary & bullets from winning profile
            tailored_summary = (
                f"Results-driven Senior Engineer targeting the {jd_obj.title} position at {jd_obj.company}. "
                f"Brings deep expertise in {', '.join(winner['matched_skills'][:4]) or 'distributed systems'}, "
                f"scaling high-throughput infrastructure, and delivering resilient microservices."
            )
            raw_bullets = []
            for exp in w_profile.get("master_experiences", []):
                raw_bullets.extend(exp.get("bullets", []))

            queue_item = {
                "id": f"job_{int(time.time()*1000)}_{len(new_items)}",
                "portal": raw.get("portal"),
                "company": raw.get("company"),
                "title": raw.get("title"),
                "salary": raw.get("salary"),
                "location": raw.get("location"),
                "url": url,
                "description": raw.get("description"),
                "selected_resume_file": winner["file_name"],
                "selected_profile_name": winner["profile_name"],
                "detected_title": winner["detected_title"],
                "match_score": winner["composite_score"],
                "matched_skills": winner["matched_skills"],
                "missing_skills": winner["missing_skills"],
                "selection_reason": winner["reason"],
                "custom_summary": tailored_summary,
                "custom_bullets": raw_bullets[:4],
                "all_evaluations_summary": [
                    {"name": e["profile_name"], "file_name": e["file_name"], "score": e["composite_score"]}
                    for e in selection_res["all_evaluations"]
                ],
                "status": "queued",
                "discovered_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            new_items.append(queue_item)
            existing_urls.add(url)

        total_queue = new_items + processed_queue
        total_queue.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        self.save_queue(total_queue)

        print(f"[+] Job Hunt complete! {len(new_items)} new qualified jobs added to the queue.")
        return total_queue

    def load_queue(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.queue_file):
            try:
                with open(self.queue_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_queue(self, queue_data: List[Dict[str, Any]]):
        with open(self.queue_file, "w", encoding="utf-8") as f:
            json.dump(queue_data, f, indent=2)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        for item in self.load_queue():
            if item.get("id") == job_id or item.get("url") == job_id:
                return item
        return None

    def update_job_customization(self, job_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Saves user customizations (summary, bullets, selected resume, url) and regenerates PDF."""
        queue = self.load_queue()
        target = None
        for item in queue:
            if item.get("id") == job_id:
                target = item
                break

        if not target:
            raise ValueError(f"Job ID '{job_id}' not found.")

        # Update fields
        if "custom_summary" in updates:
            target["custom_summary"] = updates["custom_summary"]
        if "custom_bullets" in updates:
            target["custom_bullets"] = updates["custom_bullets"]
        if "selected_resume_file" in updates:
            target["selected_resume_file"] = updates["selected_resume_file"]
        if "url" in updates and updates["url"].strip():
            target["url"] = updates["url"].strip()

        # Recalculate match score if resume file changed
        selected_prof = self.resume_bank.get_profile_by_name(target["selected_resume_file"])
        if selected_prof:
            target["selected_profile_name"] = selected_prof.get("profile_name")
            target["detected_title"] = selected_prof.get("title")

        # Compile freshly customized PDF immediately
        from .bot import JobApplicationBot
        bot = JobApplicationBot(config_dir=self.config_dir)
        jd_obj = self.jd_parser.parse_from_text(
            text=target.get("description", "") + " " + target["title"],
            title=target["title"],
            company=target["company"],
            url=target.get("url")
        )
        customizations = {
            "summary": target.get("custom_summary"),
            "bullets": target.get("custom_bullets"),
            "role": target["title"],
            "company": target["company"]
        }
        tailored = bot.process_and_tailor(
            jd_input=target.get("description", "") + " " + target["title"],
            profile=selected_prof,
            customizations=customizations
        )
        target["custom_pdf_path"] = tailored.pdf_path
        target["custom_html_path"] = tailored.html_path
        target["match_score"] = tailored.ats_score

        self.save_queue(queue)
        return target

    def add_custom_job(self, company: str, title: str, url: str, salary: str, description: str) -> Dict[str, Any]:
        """Allows user to manually input any real job opening URL and JD."""
        jd_obj = self.jd_parser.parse_from_text(
            text=description or title,
            title=title,
            company=company,
            url=url
        )
        selection_res = self.selector.select_best_profile(jd_obj)
        winner = selection_res["winner"]
        w_profile = winner["profile"]

        raw_bullets = []
        for exp in w_profile.get("master_experiences", []):
            raw_bullets.extend(exp.get("bullets", []))

        queue_item = {
            "id": f"custom_job_{int(time.time()*1000)}",
            "portal": "Direct Application",
            "company": company,
            "title": title,
            "salary": salary or "40 - 50 LPA",
            "location": "India / Remote",
            "url": url,
            "description": description or f"Role for {title} at {company}",
            "selected_resume_file": winner["file_name"],
            "selected_profile_name": winner["profile_name"],
            "detected_title": winner["detected_title"],
            "match_score": winner["composite_score"],
            "matched_skills": winner["matched_skills"],
            "missing_skills": winner["missing_skills"],
            "selection_reason": winner["reason"],
            "custom_summary": f"Results-driven Senior Engineer targeting the {title} position at {company}.",
            "custom_bullets": raw_bullets[:4],
            "all_evaluations_summary": [
                {"name": e["profile_name"], "file_name": e["file_name"], "score": e["composite_score"]}
                for e in selection_res["all_evaluations"]
            ],
            "status": "queued",
            "discovered_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        queue = self.load_queue()
        queue.insert(0, queue_item)
        self.save_queue(queue)
        return queue_item

    def apply_single_job(self, job_id: str, review_mode: bool = False, interactive: bool = False) -> Dict[str, Any]:
        """Applies to a specific job from the queue using its customized selected resume."""
        queue = self.load_queue()
        target = None
        for item in queue:
            if item.get("id") == job_id or item.get("url") == job_id:
                target = item
                break

        if not target:
            raise ValueError(f"Job ID '{job_id}' not found in queue.")

        from .bot import JobApplicationBot
        bot = JobApplicationBot(config_dir=self.config_dir)

        # Retrieve selected base profile
        selected_prof = self.resume_bank.get_profile_by_name(target.get("selected_resume_file", ""))
        
        # Prepare custom inputs if modified by user
        customizations = {
            "summary": target.get("custom_summary"),
            "bullets": target.get("custom_bullets"),
            "role": target["title"],
            "company": target["company"]
        }

        print(f"\n[*] Applying to '{target['title']}' at '{target['company']}' ({target.get('portal', '')})")
        print(f"[*] Base Resume: {target.get('selected_resume_file')} | Target URL: {target['url']}")

        # Compile customized tailored resume
        tailored = bot.process_and_tailor(
            jd_input=target.get("description", "") + " " + target["title"],
            profile=selected_prof,
            customizations=customizations
        )
        tailored.target_role = target["title"]
        tailored.target_company = target["company"]

        # Run form automation without hanging
        report = bot.apply_to_job(target["url"], tailored, review_mode=review_mode, interactive=interactive)
        
        target["status"] = "applied" if report.get("status") == "success" else "attempted"
        target["applied_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        target["last_report"] = report
        self.save_queue(queue)
        return report

    def trigger_bulk_apply_async(self, job_ids: List[str]):
        """Launches bulk apply in a background thread with live state reporting."""
        if self.bulk_state["is_running"]:
            return {"status": "already_running", "message": "Bulk apply is already running."}

        self.bulk_state = {
            "is_running": True,
            "total": len(job_ids),
            "completed": 0,
            "current_company": "",
            "results": [],
            "error": None
        }

        def worker():
            try:
                for jid in job_ids:
                    job = self.get_job(jid)
                    if not job:
                        continue
                    self.bulk_state["current_company"] = job.get("company", "Company")
                    try:
                        rep = self.apply_single_job(jid, review_mode=False, interactive=False)
                        self.bulk_state["results"].append({
                            "id": jid,
                            "company": job.get("company"),
                            "status": rep.get("status", "success"),
                            "message": rep.get("message", "Applied successfully")
                        })
                    except Exception as err:
                        self.bulk_state["results"].append({
                            "id": jid,
                            "company": job.get("company"),
                            "status": "error",
                            "message": str(err)
                        })
                    self.bulk_state["completed"] += 1
                    time.sleep(2)
            except Exception as e:
                self.bulk_state["error"] = str(e)
            finally:
                self.bulk_state["is_running"] = False
                self.bulk_state["current_company"] = ""

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        return {"status": "started", "total": len(job_ids)}
