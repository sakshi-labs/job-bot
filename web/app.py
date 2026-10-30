"""
Flask Web Interface for the Job Application Bot.
Enhanced with Per-Job Resume Customization, Single-Click Apply, and Background Bulk-Apply.
"""
import os
import sys
import json
from flask import Flask, render_template, request, jsonify, send_file

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.bot import JobApplicationBot
from src.job_hunter import JobHunter
from src.resume_bank import ResumeBank

app = Flask(__name__, template_folder="templates")
bot = JobApplicationBot(config_dir=os.path.join(PROJECT_ROOT, "config"))
hunter = JobHunter(PROJECT_ROOT)
bank = ResumeBank(resumes_dir=os.path.join(PROJECT_ROOT, "resumes"))

current_resume = None

@app.route("/")
def index():
    with open(bot.profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)
    bank.load_all()
    resumes = bank.get_profiles()
    queue = hunter.load_queue()
    return render_template("index.html", profile=profile_data, resumes=resumes, queue=queue)

@app.route("/api/resumes", methods=["GET"])
def api_get_resumes():
    bank.load_all()
    profiles = bank.get_profiles()
    summary = []
    for p in profiles:
        summary.append({
            "file_name": p.get("file_name"),
            "profile_name": p.get("profile_name"),
            "title": p.get("title"),
            "skills": p.get("skills", [])[:10]
        })
    return jsonify(summary)

@app.route("/api/hunter/hunt", methods=["POST"])
def api_hunt():
    data = request.json or {}
    query = data.get("query", "Backend")
    location = data.get("location", "Bangalore")
    limit = int(data.get("limit", 3))
    
    queue = hunter.hunt_jobs(query=query, location=location, limit_per_portal=limit)
    return jsonify({"success": True, "count": len(queue), "queue": queue})

@app.route("/api/hunter/queue", methods=["GET"])
def api_get_queue():
    queue = hunter.load_queue()
    return jsonify(queue)

@app.route("/api/hunter/add-job", methods=["POST"])
def api_add_job():
    data = request.json or {}
    company = data.get("company", "").strip()
    title = data.get("title", "").strip()
    url = data.get("url", "").strip()
    salary = data.get("salary", "40 - 50 LPA").strip()
    description = data.get("description", "").strip()

    if not company or not title:
        return jsonify({"error": "Company and Role Title are required"}), 400

    new_job = hunter.add_custom_job(company=company, title=title, url=url, salary=salary, description=description)
    return jsonify({"success": True, "job": new_job})

@app.route("/api/hunter/customize/<job_id>", methods=["GET"])
def api_get_job_customization(job_id):
    job = hunter.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    bank.load_all()
    all_resumes = [{"file_name": p.get("file_name"), "title": p.get("title")} for p in bank.get_profiles()]
    
    return jsonify({
        "job": job,
        "available_resumes": all_resumes,
        "pdf_url": f"/api/download/custom-pdf/{job_id}" if job.get("custom_pdf_path") else None
    })

@app.route("/api/hunter/customize/<job_id>", methods=["POST"])
def api_update_job_customization(job_id):
    data = request.json or {}
    try:
        updated_job = hunter.update_job_customization(job_id, data)
        return jsonify({
            "success": True,
            "job": updated_job,
            "pdf_url": f"/api/download/custom-pdf/{job_id}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/download/custom-pdf/<job_id>")
def download_custom_pdf(job_id):
    job = hunter.get_job(job_id)
    if job and job.get("custom_pdf_path") and os.path.exists(job["custom_pdf_path"]):
        return send_file(job["custom_pdf_path"], as_attachment=True, download_name=os.path.basename(job["custom_pdf_path"]))
    return "Customized PDF not compiled yet.", 404

@app.route("/api/hunter/apply", methods=["POST"])
def api_apply_job():
    data = request.json or {}
    job_id = data.get("job_id")
    if not job_id:
        return jsonify({"error": "job_id is required"}), 400

    try:
        report = hunter.apply_single_job(job_id, review_mode=False, interactive=False)
        final_status = report.get("status", "not_applied")   # "applied" | "not_applied" | "error"
        return jsonify({
            "success": final_status == "applied",
            "status": final_status,
            "error_reason": report.get("error_reason"),
            "fields_filled": report.get("fields_filled", []),
            "report": report,
        })
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route("/api/hunter/bulk-apply", methods=["POST"])
def api_bulk_apply():
    data = request.json or {}
    job_ids = data.get("job_ids", [])
    if not job_ids:
        # Default to all queued jobs
        queue = hunter.load_queue()
        job_ids = [j["id"] for j in queue if j.get("status") == "queued"]

    if not job_ids:
        return jsonify({"error": "No jobs selected or queued for bulk apply."}), 400

    res = hunter.trigger_bulk_apply_async(job_ids)
    return jsonify(res)

@app.route("/api/hunter/bulk-status", methods=["GET"])
def api_bulk_status():
    return jsonify(hunter.bulk_state)


@app.route("/api/launch-chrome", methods=["POST"])
def api_launch_chrome():
    """
    Pre-warms the shared Chrome session so the user can log into job portals
    before clicking Apply. The bot will reuse the same browser window/profile.
    """
    try:
        from src.chrome_session import ChromeSessionManager
        driver = ChromeSessionManager.get_driver(headless=False)
        # Navigate to a neutral page so the user can see the window is ready
        if len(driver.window_handles) == 1:
            driver.get("https://www.google.com")
        return jsonify({
            "success": True,
            "message": (
                "Chrome is ready! A browser window has opened. "
                "Please log into LinkedIn, Naukri, Instahyre, and any other portals. "
                "The bot will reuse your login session when you click Apply."
            )
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/hunter/mark-applied/<job_id>", methods=["POST"])
def api_mark_applied(job_id):
    """
    Manually marks a job as 'applied' when the user has submitted the form in the
    browser tab that the bot left open. Updates the queue and the applied registry.
    """
    queue = hunter.load_queue()
    target = None
    for item in queue:
        if item.get("id") == job_id or item.get("url") == job_id:
            target = item
            break

    if not target:
        return jsonify({"error": f"Job ID '{job_id}' not found."}), 404

    target["status"] = "applied"
    target["applied_at"] = __import__("time").strftime("%Y-%m-%d %H:%M:%S")
    target.pop("error_reason", None)
    hunter.save_queue(queue)

    # Also add to the bot's applied registry so it won't re-apply
    bot.mark_as_applied(job_id=job_id, job_url=target.get("url", ""))

    return jsonify({"success": True, "job_id": job_id, "status": "applied"})


@app.route("/api/hunter/reset-queue", methods=["POST"])
def api_reset_queue():
    """Resets stale 'applied' statuses back to 'queued' for re-processing."""
    data = request.json or {}
    reset_all = data.get("reset_all", False)
    queue = hunter.load_queue()
    count = 0
    for j in queue:
        if reset_all or j.get("status") in ("applied", "attempted", "error"):
            j["status"] = "queued"
            j.pop("error_reason", None)
            j.pop("applied_at", None)
            j.pop("attempted_at", None)
            j.pop("last_report", None)
            count += 1
    hunter.save_queue(queue)
    return jsonify({"success": True, "reset_count": count})

@app.route("/api/tailor", methods=["POST"])
def api_tailor():
    global current_resume
    data = request.json or {}
    jd_text = data.get("jd_text", "").strip()
    jd_url = data.get("jd_url", "").strip()

    if not jd_text and not jd_url:
        return jsonify({"error": "Please provide either a Job URL or paste Job Description text"}), 400

    target_input = jd_url if jd_url else jd_text
    is_url = bool(jd_url)

    try:
        tailored = bot.process_and_tailor(target_input, is_url=is_url)
        current_resume = tailored
        return jsonify({
            "success": True,
            "target_role": tailored.target_role,
            "target_company": tailored.target_company,
            "ats_score": tailored.ats_score,
            "matched_keywords": tailored.matched_keywords,
            "missing_keywords": tailored.missing_keywords,
            "tailored_summary": tailored.tailored_summary,
            "pdf_url": "/api/download/pdf",
            "html_url": "/api/view/html"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/download/pdf")
def download_pdf():
    global current_resume
    if current_resume and current_resume.pdf_path and os.path.exists(current_resume.pdf_path):
        return send_file(current_resume.pdf_path, as_attachment=True, download_name=os.path.basename(current_resume.pdf_path))
    return "PDF not found. Please tailor a resume first.", 404

@app.route("/api/view/html")
def view_html():
    global current_resume
    if current_resume and current_resume.html_path and os.path.exists(current_resume.html_path):
        with open(current_resume.html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "HTML not found. Please tailor a resume first.", 404

def run_app(port=5050):
    print(f"\n=======================================================")
    print(f"🚀 Job Application Bot Dashboard running at:")
    print(f"   http://127.0.0.1:{port}")
    print(f"=======================================================\n")
    app.run(host="127.0.0.1", port=port, debug=False)

if __name__ == "__main__":
    run_app()
