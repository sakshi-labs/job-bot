"""
Resume Bank Manager.
Scans the `resumes/` folder, ingests multiple distinct resume profiles (PDF/DOCX/TXT/JSON),
and provides structured access to the candidate's different personas.
"""
import os
import glob
from typing import List, Dict, Any, Optional
from .resume_parser import ResumeDocumentParser

class ResumeBank:
    def __init__(self, resumes_dir: str = "resumes", fallback_profile_path: Optional[str] = None):
        self.resumes_dir = resumes_dir
        self.fallback_profile_path = fallback_profile_path
        self.profiles: List[Dict[str, Any]] = []
        self.load_all()

    def load_all(self):
        """Discovers and parses all resumes in the resumes/ directory."""
        self.profiles = []
        if not os.path.exists(self.resumes_dir):
            os.makedirs(self.resumes_dir, exist_ok=True)

        supported_exts = ["*.pdf", "*.docx", "*.json", "*.txt", "*.md"]
        found_files = []
        for ext in supported_exts:
            found_files.extend(glob.glob(os.path.join(self.resumes_dir, ext)))

        for file_path in sorted(found_files):
            try:
                prof = ResumeDocumentParser.parse_file(file_path)
                self.profiles.append(prof)
            except Exception as e:
                print(f"[Warning] Failed to parse resume '{file_path}': {e}")

        # If no custom resumes are placed yet, load fallback master profile
        if not self.profiles and self.fallback_profile_path and os.path.exists(self.fallback_profile_path):
            try:
                prof = ResumeDocumentParser.parse_file(self.fallback_profile_path)
                prof["profile_name"] = "master_backend_profile"
                prof["title"] = prof.get("headline", "Senior Software Engineer")
                # Flatten skills
                flat_skills = []
                for cat, sks in prof.get("master_skills", {}).items():
                    flat_skills.extend([s.lower() for s in sks])
                prof["skills"] = flat_skills
                self.profiles.append(prof)
            except Exception as e:
                print(f"[Warning] Failed to load fallback profile: {e}")

    def get_profiles(self) -> List[Dict[str, Any]]:
        return self.profiles

    def get_profile_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        for p in self.profiles:
            if p.get("profile_name") == name or p.get("file_name") == name:
                return p
        return None
