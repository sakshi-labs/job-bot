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

        # Domain keywords mapping for the 4 core developer personas
        domains = {
            "llm": ["llm", "large language model", "generative ai", "genai", "langchain", "langgraph", "llamaindex", "rag", "retrieval augmented", "vector database", "pinecone", "chromadb", "chroma", "milvus", "qdrant", "weaviate", "embeddings", "openai", "claude", "gemini", "ai agent", "prompt engineering", "fine-tuning"],
            "frontend": ["frontend", "front-end", "react", "next.js", "nextjs", "vue", "angular", "ui", "ux", "css", "tailwind", "redux", "zustand", "web vitals", "client-side", "responsive design", "micro-frontend", "html5", "css3"],
            "backend": ["backend", "back-end", "distributed systems", "kafka", "microservices", "java", "golang", "go", "spring", "spring boot", "grpc", "low latency", "concurrency", "redis", "postgresql", "mysql", "rabbitmq"],
            "fullstack": ["full stack", "fullstack", "full-stack", "mern", "pern", "end-to-end", "react and node", "node and react", "full-cycle", "api and ui"],
            "data": ["spark", "flink", "etl", "lakehouse", "snowflake", "bigquery", "airflow", "analytics pipeline"],
            "devops": ["kubernetes", "k8s", "terraform", "sre", "infrastructure as code", "argocd", "helm", "cloud platform"]
        }

        # Weight title more heavily than body
        jd_combined = (jd_title * 3) + " " + jd_text[:1500]
        domain_counts = {}
        for d, keywords in domains.items():
            count = sum(1 for kw in keywords if re.search(r'\b' + re.escape(kw) + r'\b', jd_combined))
            domain_counts[d] = count

        # If LLM keywords are present, prioritize LLM specialization
        if domain_counts.get("llm", 0) >= 2:
            top_jd_domain = "llm"
        else:
            top_jd_domain = max(domain_counts, key=domain_counts.get) if any(domain_counts.values()) else "backend"

        # Check profile match against identified domain
        if top_jd_domain == "llm" and ("llm" in p_name or "ai" in p_name):
            score += 45.0
        elif top_jd_domain == "frontend" and "frontend" in p_name:
            score += 45.0
        elif top_jd_domain == "backend" and "backend" in p_name:
            score += 45.0
        elif top_jd_domain == "fullstack" and "fullstack" in p_name and "llm" not in p_name:
            score += 45.0
        elif top_jd_domain in p_name:
            score += 35.0
        else:
            # Partial overlaps
            overlap = sum(1 for kw in domains.get(top_jd_domain, []) if kw in p_name)
            score += min(overlap * 8, 15)

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
