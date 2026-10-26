# 🤖 40–50 LPA Autonomous Job Application Bot & Multi-Resume Optimizer

An autonomous job hunter and intelligent multi-resume selector specialized in **40–50+ LPA compensation brackets** across **Hirist, Naukri, LinkedIn, and Tier-1 Company Career Pages** (Google, Uber, Microsoft, Atlassian, Stripe, Razorpay, Swiggy, Zepto, Cred, PhonePe).

---

## 🌟 Architecture & Key Features

### 1. 5-Resume Bank (`resumes/`) & Profile Intelligence
- Store up to **5 distinct baseline resumes** (supporting `.pdf`, `.docx`, `.txt`, `.md`, `.json`):
  1. `backend_distributed_systems.txt` (Kafka, Go, Java, gRPC, Redis, Microservices)
  2. `data_engineering_streaming.txt` (Apache Spark, Flink, Kafka Streams, Snowflake, Airflow)
  3. `cloud_devops_platform.txt` (Kubernetes, Terraform, AWS/GCP, Docker, ArgoCD, CI/CD)
  4. `fullstack_systems.txt` (TypeScript, React, Next.js, Node.js, GraphQL, PostgreSQL)
  5. `tech_lead_staff_architect.txt` (System Architecture, RFCs, Leadership, 40–50L+ Staff Scope)
- **Core Skill Integrity Rule**: Evaluates every discovered job against all 5 resumes and picks the single best-aligned resume **without distorting or fabricating core skills**.

### 2. Per-Application Resume Customization & 1-Click Apply
- For any job in the queue, click **"🎨 Customize & Apply"**:
  - View the company, role, salary, and verified live application URL.
  - **Resume Persona Switcher**: Switch to any of your other 4 resumes on the fly—the ATS score updates in real time.
  - **Editable Targeted Summary**: Fine-tune the executive summary generated for that specific company.
  - **Editable Experience Bullets**: Add, reorder, or delete bullet points specifically for this application.
  - **"⚡ 1-Click Apply Now"**: Generates the custom PDF on the fly and auto-fills the application immediately.

### 3. Bulk Apply Engine
- Checkbox on each row + "Select All Jobs" toolbar.
- Click **"⚡ Bulk Apply Selected"**:
  - Runs in a non-blocking background worker.
  - Live progress tracking bar (`Applying 2/5: Zepto [Success], Razorpay [Success]...`).
  - Automatically submits using each opening's customized or best-selected resume.

### 4. Verified Live Working URLs & "Add Custom Job"
- All portal entries feature real, working, verified links (no 404s).
- Click **"➕ Add Custom Job"** in the dashboard to paste any real Greenhouse, Lever, Ashby, or company careers link; the bot evaluates it against your 5 resumes, selects the winner, and queues it instantly.

### 5. Persistent Chrome Session (Pre-Authenticated)
- Uses a persistent Chrome profile (`~/.job_bot_chrome_profile`). Log in once to Naukri, Hirist, and LinkedIn in Chrome, and the bot automatically inherits your active session and cookies without entering passwords or triggering CAPTCHAs.

---

## 📁 Project Layout

```
job-application-bot/
├── resumes/                           # 📂 Drop your 5 distinct resumes here (.pdf, .docx, .txt)
│   ├── backend_distributed_systems.txt
│   ├── data_engineering_streaming.txt
│   ├── cloud_devops_platform.txt
│   ├── fullstack_systems.txt
│   └── tech_lead_staff_architect.txt
├── src/
│   ├── resume_parser.py               # Universal parser (PDF streams, DOCX XML, JSON, TXT)
│   ├── resume_bank.py                 # Multi-profile manager
│   ├── profile_selector.py            # AI & heuristic selector with core-skill integrity check
│   ├── job_hunter.py                  # Master 40–50 LPA hunter, customization & bulk-apply
│   ├── chrome_session.py              # Persistent authenticated Chrome profile manager
│   ├── scrapers/                      # Hirist, Naukri, LinkedIn, and Career Pages scrapers
│   ├── ats_pdf.py                     # Zero-dependency ATS-compliant vector PDF compiler
│   └── bot.py                         # Automated application & form filler
├── web/
│   ├── app.py                         # Flask Web Dashboard backend
│   └── templates/index.html           # Modern 3-tab UI with customization modal & bulk apply
├── config/
│   ├── master_profile.json            # Contact details, screening Q&A (work auth, notice period)
│   └── settings.json                  # CTC brackets (40-50 LPA), locations, and thresholds
└── cli.py                             # Unified Command-Line Interface
```

---

## 🚀 How to Run

### 1. Launch the Interactive Web Dashboard (Recommended)
Open your terminal and run:

```bash
cd /Users/sakshimalik/Project/job-application-bot
python3 cli.py ui
```
Open **`http://127.0.0.1:5000`** in your browser to:
1. **Scan Portals**: Discover fresh 40–50 LPA openings across Hirist, Naukri, LinkedIn, and Tier-1 Career Pages.
2. **Customize & 1-Click Apply**: Click **"🎨 Customize & Apply"** on any job to edit the summary/bullets or switch resumes, then click **"⚡ 1-Click Apply Now"**.
3. **Bulk Apply**: Select multiple job checkboxes and click **"⚡ Bulk Apply Selected"** to let the background worker apply to all of them.
4. **Add Any Custom Job**: Click **"➕ Add Custom Job"** to paste any URL/JD.

---

### 2. Command Line Interface (CLI)

* **View your 5 loaded resumes**:
  ```bash
  python3 cli.py resumes
  ```

* **Scan portals for 40–50 LPA jobs**:
  ```bash
  python3 cli.py hunt --query "Backend" --loc "Bangalore"
  ```

* **View the queued jobs and selected resumes**:
  ```bash
  python3 cli.py queue
  ```

* **Add a custom opening directly from terminal**:
  ```bash
  python3 cli.py add-job --company "Stripe" --title "Staff Distributed Systems Engineer" --url "https://stripe.com/jobs/search?query=software" --salary "50 - 70 LPA" --desc "Apache Kafka, Go, distributed transactions"
  ```

* **Apply to a specific queued job**:
  ```bash
  python3 cli.py apply --job-id <job_id>
  ```

* **Run fully autonomous auto-apply for high-match jobs (≥80%)**:
  ```bash
  python3 cli.py auto --min-score 80
  ```
