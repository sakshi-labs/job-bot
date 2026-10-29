#!/usr/bin/env python3
"""
CLI entry point for the Automated Job Application & Resume Tailoring Bot.
Enhanced with Multi-Resume Bank, Profile Selector, and 30-40 LPA Autonomous Job Hunter.
"""
import sys
import os
import argparse

# Ensure project root is in sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.bot import JobApplicationBot
from src.job_hunter import JobHunter
from src.resume_bank import ResumeBank

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(
        description="Automated Job Application Bot: Multi-Resume Selector & Autonomous Job Hunter"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: hunt
    hunt_parser = subparsers.add_parser("hunt", help="Autonomously scan Instahyre, Wellfound, Workday, Hirist, Naukri & LinkedIn for 30-40 LPA jobs")
    hunt_parser.add_argument("--query", default="Full Stack", help="Target skill/role query (default: 'Full Stack')")
    hunt_parser.add_argument("--loc", default="Bangalore", help="Target location (default: 'Bangalore')")
    hunt_parser.add_argument("--limit", type=int, default=3, help="Max jobs per portal to discover")

    # Command: queue
    subparsers.add_parser("queue", help="Display discovered jobs and their matched resumes")

    # Command: resumes
    subparsers.add_parser("resumes", help="List all resumes in the resume bank and their core skills")

    # Command: auto
    auto_parser = subparsers.add_parser("auto", help="Fully autonomous apply for all queued jobs above match score threshold")
    auto_parser.add_argument("--min-score", type=float, default=80.0, help="Minimum match score threshold (default: 80.0)")

    # Command: tailor
    tailor_parser = subparsers.add_parser("tailor", help="Analyze JD and generate tailored ATS-compliant PDF & HTML")
    tailor_parser.add_argument("--jd", required=True, help="Job description text, local file path, or live URL")
    tailor_parser.add_argument("--is-url", action="store_true", help="Explicitly specify input is a URL")

    # Command: apply
    apply_parser = subparsers.add_parser("apply", help="Tailor resume and auto-fill ATS application with Human-in-the-Loop review")
    apply_parser.add_argument("--url", help="Application page URL (Greenhouse, Lever, Ashby, etc.)")
    apply_parser.add_argument("--job-id", help="Target existing queued job ID to apply with its customized resume")
    apply_parser.add_argument("--no-review", action="store_true", help="Disable pause for human verification")

    # Command: add-job
    add_parser = subparsers.add_parser("add-job", help="Add a custom job opening to the 30-40L queue")
    add_parser.add_argument("--company", required=True, help="Company name")
    add_parser.add_argument("--title", required=True, help="Job title")
    add_parser.add_argument("--url", required=True, help="Application or career URL")
    add_parser.add_argument("--salary", default="40 - 50 LPA", help="CTC band (default: 40 - 50 LPA)")
    add_parser.add_argument("--desc", default="", help="Job description text")

    # Command: ui
    ui_parser = subparsers.add_parser("ui", help="Launch interactive Web Dashboard with Job Hunter Queue")
    ui_parser.add_argument("--port", type=int, default=5050, help="Web server port (default: 5050, avoids macOS AirPlay collision)")

    # Command: test
    subparsers.add_parser("test", help="Run self-test with sample job description")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    hunter = JobHunter(root_dir)

    if args.command == "resumes":
        bank = ResumeBank(resumes_dir=os.path.join(root_dir, "resumes"))
        profiles = bank.get_profiles()
        print(f"\n==================================================================")
        print(f"📁 RESUME BANK: Found {len(profiles)} Candidate Resume Profile(s)")
        print(f"==================================================================")
        for idx, p in enumerate(profiles, 1):
            print(f"[{idx}] File: {p.get('file_name')}")
            print(f"    Profile Name: {p.get('profile_name')}")
            print(f"    Title:        {p.get('title')}")
            skills = p.get('skills', [])
            print(f"    Core Skills:  {', '.join(skills[:8]) if skills else 'General Engineering'}")
            print("-" * 66)

    elif args.command == "hunt":
        jobs = hunter.hunt_jobs(query=args.query, location=args.loc, limit_per_portal=args.limit)
        print(f"\nDiscovered {len(jobs)} jobs in 30-40 LPA band. Run `python cli.py queue` to view.")

    elif args.command == "queue":
        queue = hunter.load_queue()
        if not queue:
            print("\nQueue is empty! Run `python cli.py hunt` first to discover jobs.")
            return

        print("\n" + "="*85)
        print(f"{'STATUS':<8} | {'PORTAL':<12} | {'COMPANY':<14} | {'ROLE':<28} | {'CTC':<12} | {'MATCH':<6} | {'SELECTED RESUME'}")
        print("="*85)
        for j in queue:
            status = j.get("status", "queued").upper()
            portal = j.get("portal", "")[:11]
            comp = j.get("company", "")[:13]
            title = j.get("title", "")[:27]
            sal = j.get("salary", "")[:11]
            score = f"{j.get('match_score', 0)}%"
            res = j.get("selected_resume_file", "")[:24]
            print(f"{status:<8} | {portal:<12} | {comp:<14} | {title:<28} | {sal:<12} | {score:<6} | {res}")
        print("="*85)

    elif args.command == "auto":
        print(f"[*] Starting Fully Autonomous Auto-Apply for jobs with match score >= {args.min_score}%...")
        results = hunter.auto_apply_high_matches(min_score=args.min_score)
        print(f"[+] Autonomous run complete! Processed {len(results)} applications.")

    elif args.command == "tailor":
        bot = JobApplicationBot(config_dir=os.path.join(root_dir, "config"))
        tailored = bot.process_and_tailor(args.jd, is_url=args.is_url)
        print("\n" + "="*50)
        print(f"Candidate: {tailored.full_name}")
        print(f"Role:      {tailored.target_role} @ {tailored.target_company}")
        print(f"ATS Score: {tailored.ats_score}%")
        print(f"PDF Saved: {tailored.pdf_path}")
        print(f"HTML View: {tailored.html_path}")
        print("="*50)

    elif args.command == "add-job":
        item = hunter.add_custom_job(
            company=args.company,
            title=args.title,
            url=args.url,
            salary=args.salary,
            description=args.desc
        )
        print(f"\n[+] Successfully added '{item['title']}' at '{item['company']}' to queue!")
        print(f"    Selected Resume: {item['selected_resume_file']}")
        print(f"    ATS Match Score: {item['match_score']}%")

    elif args.command == "apply":
        if args.job_id:
            rep = hunter.apply_single_job(args.job_id, review_mode=not args.no_review, interactive=True)
            print(f"[+] Application finished with status: {rep.get('status')}")
        elif args.url:
            bot = JobApplicationBot(config_dir=os.path.join(root_dir, "config"))
            tailored = bot.process_and_tailor(args.url, is_url=True)
            bot.apply_to_job(args.url, tailored, review_mode=not args.no_review, interactive=True)
        else:
            print("[!] Please provide either --url or --job-id to apply.")

    elif args.command == "test":
        bot = JobApplicationBot(config_dir=os.path.join(root_dir, "config"))
        sample_jd_path = os.path.join(root_dir, "sample_data", "sample_jd.txt")
        print(f"[*] Running test with sample JD: {sample_jd_path}")
        tailored = bot.process_and_tailor(sample_jd_path)
        print("\n[SUCCESS] Self-test complete!")
        print(f"Generated PDF: {tailored.pdf_path}")
        print(f"ATS Match Score: {tailored.ats_score}%")

    elif args.command == "ui":
        from web.app import run_app
        run_app(port=args.port)

if __name__ == "__main__":
    main()
