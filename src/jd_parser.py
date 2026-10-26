"""
Job Description Parser and Keyword Extractor.
Scrapes and parses job postings from URLs or raw text.
"""
import re
import urllib.parse
from typing import List, Dict, Set
import requests
from bs4 import BeautifulSoup
from .models import JobDescription

COMMON_TECH_KEYWORDS = {
    # Languages
    "python", "java", "golang", "go", "c++", "c#", "rust", "javascript", "typescript", "ruby", "scala", "swift", "kotlin", "sql", "bash",
    # Frameworks & Libraries
    "react", "angular", "vue", "django", "flask", "fastapi", "spring", "spring boot", "node.js", "nodejs", "express", "next.js", "graphql",
    # Distributed Systems & Cloud
    "kafka", "apache kafka", "rabbitmq", "redis", "grpc", "microservices", "distributed systems", "event-driven",
    "aws", "amazon web services", "gcp", "google cloud", "azure", "kubernetes", "k8s", "docker", "terraform", "ci/cd",
    # Databases & Storage
    "postgresql", "postgres", "mysql", "mongodb", "dynamodb", "elasticsearch", "cassandra", "snowflake", "bigquery",
    # Practices & Concepts
    "rest", "restful", "system design", "multithreading", "concurrency", "low latency", "high throughput", "observability",
    "opentelemetry", "prometheus", "grafana", "git", "agile", "scrum", "unit testing", "load testing"
}

class JDParser:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        }

    def parse_from_url(self, url: str) -> JobDescription:
        """Fetch and extract job details from a web URL."""
        resp = requests.get(url, headers=self.headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Remove scripts, styles, headers, footers
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()
            
        title = self._extract_title(soup, url)
        company = self._extract_company(soup, url)
        text = soup.get_text(separator="\n", strip=True)
        
        return self.parse_from_text(text=text, title=title, company=company, url=url)

    def parse_from_text(self, text: str, title: str = "", company: str = "", url: str = "") -> JobDescription:
        """Parse structured details from raw JD text."""
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        if not title and lines:
            # Fallback heuristic: First non-empty header-like line
            for line in lines[:5]:
                if any(role_word in line.lower() for role_word in ["engineer", "developer", "architect", "lead", "manager"]):
                    title = line
                    break
            if not title:
                title = lines[0] if lines else "Software Engineer"
                
        if not company:
            # Look for "at <Company>" or domain
            if url:
                domain = urllib.parse.urlparse(url).netloc
                company = domain.replace("www.", "").split(".")[0].capitalize()
            else:
                company = "Hiring Company"
                
        keywords = self._extract_keywords(text)
        
        return JobDescription(
            title=title,
            company=company,
            raw_text=text,
            url=url,
            extracted_keywords=keywords,
            required_skills=keywords[:15]
        )

    def _extract_title(self, soup: BeautifulSoup, url: str) -> str:
        # Greenhouse
        gh_title = soup.find(class_=re.compile(r"app-title|job-title", re.I))
        if gh_title:
            return gh_title.get_text(strip=True)
            
        # Lever
        lever_title = soup.find(class_=re.compile(r"posting-headline", re.I))
        if lever_title and lever_title.find("h2"):
            return lever_title.find("h2").get_text(strip=True)
            
        # Ashby
        ashby_title = soup.find("h1")
        if ashby_title:
            return ashby_title.get_text(strip=True)
            
        if soup.title and soup.title.string:
            title_text = soup.title.string.strip()
            # Often formatted as "Job Title at Company" or "Job Title - Company"
            for sep in [" at ", " - ", " | "]:
                if sep in title_text:
                    return title_text.split(sep)[0].strip()
            return title_text
            
        return "Software Engineer"

    def _extract_company(self, soup: BeautifulSoup, url: str) -> str:
        # Lever
        lever_org = soup.find(class_=re.compile(r"main-header-logo", re.I))
        if lever_org and lever_org.get("alt"):
            return lever_org["alt"].replace(" logo", "")
            
        # Greenhouse
        gh_org = soup.find(class_=re.compile(r"company-name", re.I))
        if gh_org:
            return gh_org.get_text(strip=True)
            
        if url:
            domain = urllib.parse.urlparse(url).netloc
            parts = domain.replace("www.", "").split(".")
            # e.g., jobs.lever.co/company -> path has company
            path_parts = [p for p in urllib.parse.urlparse(url).path.split("/") if p]
            if "lever.co" in domain and path_parts:
                return path_parts[0].capitalize()
            if "greenhouse.io" in domain and path_parts:
                return path_parts[0].capitalize()
            if parts:
                return parts[0].capitalize()
                
        return "Target Company"

    def _extract_keywords(self, text: str) -> List[str]:
        lower_text = text.lower()
        found = set()
        for kw in COMMON_TECH_KEYWORDS:
            # Word boundary regex search
            pattern = r'\b' + re.escape(kw) + r'\b'
            if re.search(pattern, lower_text):
                found.add(kw)
        
        # Sort by frequency of occurrence in the JD
        def count_occ(w):
            return len(re.findall(r'\b' + re.escape(w) + r'\b', lower_text))
            
        sorted_kw = sorted(list(found), key=count_occ, reverse=True)
        return sorted_kw
