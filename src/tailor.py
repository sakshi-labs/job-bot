"""
Resume Tailoring Engine.
Adapts candidate master profile to match a target Job Description.
Supports LLM-powered generation (Gemini, OpenAI) with a robust heuristic offline fallback.
"""
import os
import re
import json
from typing import Dict, List, Tuple, Any, Optional
from .models import JobDescription, TailoredResume, ExperienceEntry

class ResumeTailor:
    def __init__(self, master_profile_path: str, settings_path: str):
        self.default_profile = {}
        if os.path.exists(master_profile_path):
            with open(master_profile_path, "r", encoding="utf-8") as f:
                self.default_profile = json.load(f)
        
        self.settings = {}
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as f:
                self.settings = json.load(f)

    def tailor(self, jd: JobDescription, profile: Optional[Dict[str, Any]] = None, customizations: Optional[Dict[str, Any]] = None) -> TailoredResume:
        """Main entry point to tailor the given or default resume profile to the JD."""
        active_profile = profile or self.default_profile

        # If user provided direct customizations (from UI modal), apply them directly
        if customizations:
            return self._build_customized_resume(jd, active_profile, customizations)

        # Try LLM if configured and key is available
        llm_tailored = self._try_llm_tailor(jd, active_profile)
        if llm_tailored:
            return llm_tailored
            
        # Fallback to intelligent heuristic tailoring
        return self._heuristic_tailor(jd, active_profile)

    def _build_customized_resume(self, jd: JobDescription, profile: Dict[str, Any], custom: Dict[str, Any]) -> TailoredResume:
        """Constructs a resume from explicit user edits in the web UI."""
        p = profile.get("personal", {})
        
        # Bullets
        experiences = []
        custom_bullets = custom.get("bullets", [])
        raw_exps = profile.get("master_experiences", [])
        
        if raw_exps:
            for idx, exp in enumerate(raw_exps):
                # If bullets were provided for this role
                b_list = custom_bullets if idx == 0 and custom_bullets else exp.get("bullets", [])
                experiences.append(ExperienceEntry(
                    company=exp.get("company", "Tech Co"),
                    role=exp.get("role", "Senior Software Engineer"),
                    location=exp.get("location", "Bangalore, India"),
                    start_date=exp.get("start_date", "2021"),
                    end_date=exp.get("end_date", "Present"),
                    is_current=exp.get("is_current", True),
                    bullets=b_list[:4]
                ))
        else:
            experiences.append(ExperienceEntry(
                company="Nexus Platforms",
                role=profile.get("title", "Senior Software Engineer"),
                location="Bangalore, India",
                start_date="2021",
                end_date="Present",
                is_current=True,
                bullets=custom_bullets or ["Architected distributed systems."]
            ))

        skills_dict = custom.get("skills_dict") or profile.get("master_skills", {"Core Skills": profile.get("skills", [])[:10]})
        ats_score = int(custom.get("ats_score", 92))

        return TailoredResume(
            full_name=p.get("full_name", "Alex Morgan"),
            email=p.get("email", "alex.morgan.dev@example.com"),
            phone=p.get("phone", "+91 98765 43210"),
            location=p.get("location", "Bangalore, India"),
            linkedin=p.get("linkedin", "https://linkedin.com/in/alexmorgan-dev"),
            github=p.get("github", "https://github.com/alexmorgan-dev"),
            portfolio=p.get("portfolio", "https://alexmorgandev.io"),
            target_role=jd.title or custom.get("role", "Senior Software Engineer"),
            target_company=jd.company or custom.get("company", "Target Company"),
            tailored_summary=custom.get("summary", profile.get("base_summary", "")),
            categorized_skills=skills_dict,
            experiences=experiences,
            education=profile.get("education", []),
            projects=profile.get("projects", []),
            certifications=profile.get("certifications", []),
            ats_score=ats_score,
            matched_keywords=custom.get("matched_keywords", jd.extracted_keywords[:6]),
            missing_keywords=custom.get("missing_keywords", []),
            base_profile_name=profile.get("profile_name", "custom")
        )

    def _try_llm_tailor(self, jd: JobDescription, profile: Dict[str, Any]) -> Any:
        gemini_key = os.environ.get("GEMINI_API_KEY")
        openai_key = os.environ.get("OPENAI_API_KEY")
        
        if gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel(self.settings.get("tailoring", {}).get("model_name", "gemini-1.5-flash"))
                prompt = self._build_llm_prompt(jd, profile)
                resp = model.generate_content(prompt)
                return self._parse_llm_response(resp.text, jd, profile)
            except Exception as e:
                print(f"[Warning] Gemini API call failed: {e}. Falling back to heuristic engine.")
                
        if openai_key:
            try:
                import urllib.request
                prompt = self._build_llm_prompt(jd, profile)
                payload = json.dumps({
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "You are an expert technical resume writer and ATS optimization specialist. Return strictly valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2
                }).encode("utf-8")
                req = urllib.request.Request(
                    "https://api.openai.com/v1/chat/completions",
                    data=payload,
                    headers={
                        "Authorization": f"Bearer {openai_key}",
                        "Content-Type": "application/json"
                    }
                )
                with urllib.request.urlopen(req, timeout=20) as r:
                    res_data = json.loads(r.read().decode("utf-8"))
                    content = res_data["choices"][0]["message"]["content"]
                    return self._parse_llm_response(content, jd, profile)
            except Exception as e:
                print(f"[Warning] OpenAI API call failed: {e}. Falling back to heuristic engine.")
                
        return None

    def _build_llm_prompt(self, jd: JobDescription, profile: Dict[str, Any]) -> str:
        return f"""
You are an expert ATS resume tailoring engine.
Given the candidate's active profile and the target job description, generate a tailored resume JSON.
Maintain 100% factual truth from the profile; highlight, prioritize, and phrase existing experiences to match the JD's keywords.

Target Role: {jd.title}
Target Company: {jd.company}

Job Description:
\"\"\"{jd.raw_text[:3500]}\"\"\"

Active Profile:
{json.dumps(profile, indent=2)}

Output strictly valid JSON with this exact schema:
{{
  "tailored_summary": "3-sentence professional summary targeted at {jd.company} and {jd.title}",
  "categorized_skills": {{ "CategoryName": ["Skill1", "Skill2"] }},
  "experiences": [
    {{
      "company": "Company Name",
      "role": "Role Title",
      "location": "Location",
      "start_date": "Date",
      "end_date": "Date",
      "is_current": true,
      "bullets": ["3-4 prioritized and targeted bullet points"]
    }}
  ],
  "ats_score": 88,
  "matched_keywords": ["list", "of", "matched", "keywords"],
  "missing_keywords": ["list", "of", "missing", "keywords"]
}}
"""

    def _parse_llm_response(self, text: str, jd: JobDescription, profile: Dict[str, Any]) -> TailoredResume:
        clean_json = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        data = json.loads(clean_json)
        
        experiences = []
        for exp in data.get("experiences", []):
            experiences.append(ExperienceEntry(
                company=exp["company"],
                role=exp["role"],
                location=exp["location"],
                start_date=exp["start_date"],
                end_date=exp["end_date"],
                is_current=exp.get("is_current", False),
                bullets=exp["bullets"]
            ))
            
        p = profile.get("personal", {})
        return TailoredResume(
            full_name=p.get("full_name", "Alex Morgan"),
            email=p.get("email", "alex.morgan.dev@example.com"),
            phone=p.get("phone", "+91 98765 43210"),
            location=p.get("location", "Bangalore, India"),
            linkedin=p.get("linkedin", "https://linkedin.com/in/alexmorgan-dev"),
            github=p.get("github", "https://github.com/alexmorgan-dev"),
            portfolio=p.get("portfolio", ""),
            target_role=jd.title,
            target_company=jd.company,
            tailored_summary=data["tailored_summary"],
            categorized_skills=data["categorized_skills"],
            experiences=experiences,
            education=profile.get("education", []),
            projects=profile.get("projects", []),
            certifications=profile.get("certifications", []),
            ats_score=int(data.get("ats_score", 85)),
            matched_keywords=data.get("matched_keywords", []),
            missing_keywords=data.get("missing_keywords", []),
            base_profile_name=profile.get("profile_name", "custom")
        )

    def _heuristic_tailor(self, jd: JobDescription, profile: Dict[str, Any]) -> TailoredResume:
        """Offline rule-based tailoring using the active profile."""
        jd_keywords = set(k.lower() for k in jd.extracted_keywords)
        p = profile.get("personal", {})
        
        # 1. Match skills from profile
        candidate_skills = {}
        all_candidate_skills_flat = []
        matched_kw = set()

        raw_skills = profile.get("master_skills") or {"Core Skills": profile.get("skills", [])}
        for category, skills in raw_skills.items():
            matching_in_cat = []
            other_in_cat = []
            
            for s in skills:
                all_candidate_skills_flat.append(s.lower())
                if s.lower() in jd_keywords or any(re.search(r'\b' + re.escape(k) + r'\b', s.lower()) for k in jd_keywords):
                    matching_in_cat.append(s)
                    matched_kw.add(s.lower())
                else:
                    other_in_cat.append(s)
            
            # Put matching skills first
            candidate_skills[category] = matching_in_cat + other_in_cat

        missing_kw = [k for k in jd.extracted_keywords if k.lower() not in all_candidate_skills_flat]
        
        # Calculate ATS match score
        total_jd_kw = max(len(jd.extracted_keywords), 1)
        raw_score = int((len(matched_kw) / total_jd_kw) * 100)
        ats_score = min(max(raw_score + 40, 50), 96)
        
        # 2. Prioritize experience bullet points from active profile
        max_bullets = self.settings.get("tailoring", {}).get("max_bullets_per_job", 4)
        tailored_experiences = []
        
        for exp in profile.get("master_experiences", []):
            scored_bullets = []
            for bullet in exp.get("bullets", []):
                bullet_lower = bullet.lower()
                score = sum(2.0 for kw in jd_keywords if re.search(r'\b' + re.escape(kw) + r'\b', bullet_lower))
                scored_bullets.append((score, bullet))
                
            scored_bullets.sort(key=lambda x: x[0], reverse=True)
            chosen_bullets = [b[1] for b in scored_bullets[:max_bullets]]
            
            tailored_experiences.append(ExperienceEntry(
                company=exp["company"],
                role=exp["role"],
                location=exp.get("location", "Bangalore, India"),
                start_date=exp.get("start_date", "2021"),
                end_date=exp.get("end_date", "Present"),
                is_current=exp.get("is_current", False),
                bullets=chosen_bullets or exp.get("bullets", [])[:3]
            ))
            
        # 3. Formulate tailored professional summary
        top_skills = [s.title() for s in list(matched_kw)[:4]]
        skills_str = ", ".join(top_skills) if top_skills else "high-scale distributed systems and architecture"
        
        target_role_clean = jd.title if jd.title else profile.get("title", "Senior Software Engineer")
        target_comp_clean = jd.company if jd.company else "Target Company"

        tailored_summary = (
            f"Results-driven Senior Engineer targeting the {target_role_clean} position at {target_comp_clean}. "
            f"Brings deep expertise in {skills_str}, with a proven track record of scaling low-latency "
            f"backend infrastructure, optimizing distributed data pipelines, and delivering resilient microservices."
        )
        
        return TailoredResume(
            full_name=p.get("full_name", "Alex Morgan"),
            email=p.get("email", "alex.morgan.dev@example.com"),
            phone=p.get("phone", "+91 98765 43210"),
            location=p.get("location", "Bangalore, India"),
            linkedin=p.get("linkedin", "https://linkedin.com/in/alexmorgan-dev"),
            github=p.get("github", "https://github.com/alexmorgan-dev"),
            portfolio=p.get("portfolio", "https://alexmorgandev.io"),
            target_role=target_role_clean,
            target_company=target_comp_clean,
            tailored_summary=tailored_summary,
            categorized_skills=candidate_skills,
            experiences=tailored_experiences,
            education=profile.get("education", []),
            projects=profile.get("projects", []),
            certifications=profile.get("certifications", []),
            ats_score=ats_score,
            matched_keywords=list(matched_kw),
            missing_keywords=missing_kw[:8],
            base_profile_name=profile.get("profile_name", "custom")
        )
