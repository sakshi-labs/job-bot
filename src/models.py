"""
Data models for the Job Application Bot.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class JobDescription:
    title: str = ""
    company: str = ""
    location: str = ""
    raw_text: str = ""
    url: Optional[str] = None
    extracted_keywords: List[str] = field(default_factory=list)
    required_skills: List[str] = field(default_factory=list)
    seniority: str = ""

@dataclass
class ExperienceEntry:
    company: str
    role: str
    location: str
    start_date: str
    end_date: str
    is_current: bool
    bullets: List[str]
    relevance_score: float = 0.0

@dataclass
class TailoredResume:
    full_name: str
    email: str
    phone: str
    location: str
    linkedin: str
    github: str
    portfolio: str
    target_role: str
    target_company: str
    tailored_summary: str
    categorized_skills: Dict[str, List[str]]
    experiences: List[ExperienceEntry]
    education: List[Dict[str, Any]]
    projects: List[Dict[str, Any]]
    certifications: List[str]
    ats_score: int
    matched_keywords: List[str]
    missing_keywords: List[str]
    pdf_path: Optional[str] = None
    html_path: Optional[str] = None
    base_profile_name: str = ""
