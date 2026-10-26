"""
Multi-Profile Resume Selector.
Evaluates a target job opening against all candidate profiles in the resume bank.
Selects the best-aligned resume to maximize ATS score while strictly preserving
the core authentic skills without distortion or hallucination.
"""
import re
from typing import List, Dict, Any, Tuple
from .models import JobDescription

class ProfileSelector:
    def __init__(self, resume_bank):
        self.resume_bank = resume_bank

    def select_best_profile(self, jd: JobDescription) -> Dict[str, Any]:
        """
        Compares JD against all resumes in the bank and ranks them.
        Returns the top profile, its alignment score, and a comparison table.
        """
        profiles = self.resume_bank.get_profiles()
        if not profiles:
            raise ValueError("No resumes found in the resume bank! Please place resumes in resumes/")

        jd_text_lower = jd.raw_text.lower()
        jd_keywords = set(k.lower() for k in jd.extracted_keywords)
        jd_title_lower = jd.title.lower()

        evaluations = []

        for p in profiles:
            p_skills = set(s.lower() for s in p.get("skills", []))
            p_text_lower = p.get("raw_text", "").lower()
            p_title_lower = p.get("title", "").lower()

            # 1. Core Skills Match Score (0 - 100)
            if jd_keywords:
                matched_skills = [k for k in jd_keywords if k in p_skills or re.search(r'\b' + re.escape(k) + r'\b', p_text_lower)]
                skill_match_ratio = len(matched_skills) / max(len(jd_keywords), 1)
            else:
                matched_skills = []
                skill_match_ratio = 0.5
            core_skill_score = min(skill_match_ratio * 100, 100)

            # 2. Domain & Specialization Alignment Score (0 - 100)
            domain_score = self._compute_domain_alignment(jd_title_lower, jd_text_lower, p.get("profile_name", ""), p_title_lower)

            # 3. Seniority & Scope Alignment (Staff/Principal/Lead vs Senior)
            seniority_score = self._compute_seniority_alignment(jd_title_lower, jd_text_lower, p_title_lower, p_text_lower)

            # Weighted Composite Alignment Score
            # 45% Core Skills + 35% Domain Specialization + 20% Seniority
            composite_score = (0.45 * core_skill_score) + (0.35 * domain_score) + (0.20 * seniority_score)
            composite_score = round(min(max(composite_score, 15), 98), 1)

            # Missing core skills that the JD asks for which this resume lacks
            missing_skills = [k for k in list(jd_keywords)[:10] if k not in p_skills and not re.search(r'\b' + re.escape(k) + r'\b', p_text_lower)]

            evaluations.append({
                "profile": p,
                "profile_name": p.get("profile_name", p.get("file_name")),
                "file_name": p.get("file_name"),
                "file_path": p.get("file_path"),
                "detected_title": p.get("title"),
                "composite_score": composite_score,
                "core_skill_score": round(core_skill_score, 1),
                "domain_score": round(domain_score, 1),
                "matched_skills": matched_skills,
                "missing_skills": missing_skills,
                "reason": self._generate_selection_reason(p.get("profile_name", ""), composite_score, matched_skills)
            })

        # Sort descending by composite alignment score
        evaluations.sort(key=lambda x: x["composite_score"], reverse=True)
        winner = evaluations[0]

        return {
            "winner": winner,
            "all_evaluations": evaluations,
            "total_profiles_evaluated": len(evaluations),
            "target_role": jd.title,
            "target_company": jd.company
        }

    def _compute_domain_alignment(self, jd_title: str, jd_text: str, profile_name: str, p_title: str) -> float:
        score = 50.0
        p_name = profile_name.lower() + " " + p_title.lower()

        # Domain keywords mapping
        domains = {
            "data": ["data", "spark", "flink", "etl", "lakehouse", "snowflake", "bigquery", "airflow", "analytics", "pipeline"],
            "devops": ["devops", "cloud", "platform", "kubernetes", "k8s", "terraform", "sre", "infrastructure", "argocd", "helm"],
            "fullstack": ["full stack", "fullstack", "react", "next.js", "frontend", "typescript", "node.js", "graphql", "ui"],
            "backend": ["backend", "distributed systems", "kafka", "microservices", "low latency", "concurrency", "golang", "java"],
            "staff": ["staff", "principal", "architect", "tech lead", "engineering leadership", "system design", "rfc"]
        }

        # Identify JD primary domain
        jd_combined = jd_title + " " + jd_text[:1200]
        domain_counts = {}
        for d, keywords in domains.items():
            count = sum(1 for kw in keywords if kw in jd_combined)
            domain_counts[d] = count

        top_jd_domain = max(domain_counts, key=domain_counts.get) if domain_counts else "backend"

        # Check if profile matches the top JD domain
        if top_jd_domain in p_name:
            score += 40.0
        else:
            # Partial overlaps
            overlap = sum(1 for kw in domains.get(top_jd_domain, []) if kw in p_name)
            score += min(overlap * 10, 20)

        return min(score, 100.0)

    def _compute_seniority_alignment(self, jd_title: str, jd_text: str, p_title: str, p_text: str) -> float:
        is_staff_jd = any(lvl in jd_title for lvl in ["staff", "principal", "director", "lead", "architect", "head"])
        is_staff_profile = any(lvl in p_title.lower() for lvl in ["staff", "principal", "lead", "architect"])

        if is_staff_jd and is_staff_profile:
            return 95.0
        elif not is_staff_jd and not is_staff_profile:
            return 90.0
        elif is_staff_jd and not is_staff_profile:
            return 65.0 # Senior applying for Staff
        else:
            return 80.0 # Staff applying for Senior
            
    def _generate_selection_reason(self, profile_name: str, score: float, matched_skills: List[str]) -> str:
        top_skills = ", ".join(matched_skills[:4]) if matched_skills else "general engineering principles"
        return f"Aligned with score {score}% based on high overlap in: {top_skills}."
