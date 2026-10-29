# 🤖 Multi-Platform Job Application Bot & 4-Resume Optimizer (30–40 LPA)

An intelligent multi-resume job hunting and application automation platform specialized in **₹30 – ₹40+ Lakhs P.A.** software engineering opportunities across:
- **Instahyre** (Curated AI invite platform in India)
- **Wellfound / AngelList** (Top startup & AI/LLM platform)
- **Workday & Enterprise Career Portals** (Walmart, Adobe, Salesforce, Nvidia, Cisco, Google, Microsoft)
- **Hirist & Naukri** (30–40 LPA tech filters)
- **LinkedIn Jobs** (Senior/Lead/Staff software engineer roles)

---

## 🌟 The 4 Developer Resumes (`resumes/`)

The bot manages **four specialized developer personas**, dynamically selecting the highest-scoring ATS resume without distorting your authentic skills:

1. **`frontend_engineering.txt` (Frontend Specialist)**:
   - React 18/19, Next.js (App Router, Server Actions), TypeScript, Tailwind CSS, Redux Toolkit, Zustand, React Query, Webpack/Vite, Core Web Vitals, Micro-frontends, UI/UX Component Architecture.
2. **`backend_development.txt` (Backend Specialist)**:
   - Java (Spring Boot), Go (Golang), Python, Microservices, Apache Kafka, gRPC, Redis, PostgreSQL, MySQL, Distributed Systems, Concurrency, Low-Latency / High-Throughput systems, Docker, AWS.
3. **`fullstack_development.txt` (Full Stack Generalist)**:
   - End-to-end web applications: React/Next.js on frontend, Node.js/Go/Python on backend, REST & GraphQL APIs, PostgreSQL, MongoDB, Redis, Docker, AWS, CI/CD, full-cycle product engineering.
4. **`fullstack_llm_ai_development.txt` (Full Stack AI & LLM Specialist)**:
   - Generative AI & Large Language Models: LangChain, LangGraph, LlamaIndex, RAG (Retrieval Augmented Generation), OpenAI/Claude/Gemini APIs, Vector DBs (Pinecone, ChromaDB, pgvector), Vercel AI SDK, Streaming UI, Prompt Engineering, FastAPI, Next.js.

---

## 🚀 Key Features

### 1. Workday Enterprise ATS Automation (`src/forms/workday.py`)
- Detects `*.myworkdayjobs.com` and Workday multi-step application wizards.
- Automates initial "Apply" / "Autofill with Resume" triggers.
- Uploads the dynamically compiled vector PDF to Workday dropzones.
- Fills Legal Name, Contact Information, Address, City, Postal Code, Phone, and Email.
- Answers standard Workday questionnaires (work authorization, sponsorship, notice period).
- Advances through pagination (`bottom-navigation-next-button`) to the review screen.

### 2. Multi-Platform Coverage (30–40 LPA)
- **Instahyre**: The #1 recruiter reach-out platform in India for 30–40L roles.
- **Wellfound**: Global startups and remote GenAI / LLM teams paying $50k–$85k (₹30L–₹40L+).
- **Workday (BigTech)**: Direct integration with Fortune 500 portals (Walmart, Adobe, Salesforce, Nvidia, Cisco).
- **Naukri & Hirist**: Search algorithms tuned for 30–40 Lakhs salary brackets.
- **LinkedIn**: Staff & Senior engineering searches using persistent session cookies.

### 3. Per-Application Customization & 1-Click Apply
- In the dashboard, click **"🎨 Customize & Apply"** on any job:
  - **Resume Switcher**: Seamlessly switch between the 4 resumes on the fly—the ATS match score recomputes in real time.
  - **Editable Targeted Summary**: Tailored specifically for that company & role.
  - **Editable Bullet Points**: Add, delete, or refine prioritized bullet points for that application.
  - **"⚡ 1-Click Apply Now"**: Generates the custom PDF on the fly and auto-fills the application immediately.

### 4. Background Bulk Apply Engine
- Select multiple jobs via row checkboxes or "Select All".
- Click **"⚡ Bulk Apply Selected"**:
  - Executes in a non-blocking background worker (`threading.Thread`).
  - Displays live progress: `Applying 2/4: Zepto [Success], Razorpay [Success]...`

---

## 📁 Project Layout

```
job-application-bot/
├── resumes/                           # 📂 4 Core Resumes (.txt, .pdf, .docx)
│   ├── frontend_engineering.txt       # React, Next.js, TypeScript, UI/UX
│   ├── backend_development.txt        # Java, Go, Kafka, Distributed Systems
│   ├── fullstack_development.txt      # React, Node.js, Python, Databases, AWS
│   └── fullstack_llm_ai_development.txt # GenAI, LLMs, LangChain, RAG, Vector DBs
├── src/
│   ├── resume_parser.py               # Ingests PDF streams, DOCX XML, and TXT
│   ├── resume_bank.py                 # Multi-profile manager
│   ├── profile_selector.py            # AI selector matching Frontend, Backend, Full Stack & LLM
│   ├── job_hunter.py                  # Master hunter across Instahyre, Wellfound, Workday, etc.
│   ├── chrome_session.py              # Persistent authenticated Chrome profile
│   ├── scrapers/
│   │   ├── instahyre.py               # Instahyre 30-40L portal
│   │   ├── wellfound.py               # Wellfound startup & AI portal
│   │   ├── career_pages.py            # Workday (Walmart, Adobe, Salesforce) & BigTech
│   │   ├── hirist.py                  # Hirist 30-40 LPA filter
│   │   ├── naukri.py                  # Naukri 30-40 Lacs filter
│   │   └── linkedin.py                # LinkedIn senior roles
│   ├── forms/
│   │   ├── workday.py                 # Workday multi-step enterprise automation
│   │   ├── greenhouse.py              # Greenhouse ATS automation
│   │   ├── lever.py                   # Lever ATS automation
│   │   ├── ashby.py                   # Ashby ATS automation
│   │   └── generic.py                 # Fallback heuristic form filler
│   ├── ats_pdf.py                     # Zero-dependency ATS vector PDF compiler
│   └── bot.py                         # Master browser automation runner
├── web/
│   ├── app.py                         # Flask Web Dashboard backend (Port 5050)
│   └── templates/index.html           # 3-Tab UI with customization modal & bulk apply
├── config/
│   ├── master_profile.json            # Contact details, screening Q&A
│   └── settings.json                  # CTC brackets (30-40 LPA), portals, thresholds
└── cli.py                             # Unified CLI
```

---

## 💻 How to Run

### Method 1: Interactive Web Dashboard (Recommended)
Open your terminal and run:

```bash
cd /Users/sakshimalik/Project/job-application-bot
python3 cli.py ui
```
Navigate to **[http://127.0.0.1:5050](http://127.0.0.1:5050)** in Chrome / Safari.
- Click **"🔍 Scan Portals"** to discover 30–40 LPA jobs across Instahyre, Wellfound, Workday, Hirist, Naukri, and LinkedIn.
- Inspect the queue table to see which of the 4 resumes was matched.
- Click **"🎨 Customize & Apply"** to tweak the resume or **"⚡ 1-Click Apply"** to apply directly.
- Select checkboxes and click **"⚡ Bulk Apply Selected"** for batch applications.

---

### Method 2: Command Line Interface (CLI)

* **View your 4 loaded resumes**:
  ```bash
  python3 cli.py resumes
  ```

* **Scan portals for 30–40 LPA jobs**:
  ```bash
  python3 cli.py hunt --query "Full Stack" --loc "Bangalore"
  ```

* **View the queued jobs and selected resumes**:
  ```bash
  python3 cli.py queue
  ```

* **Apply to a specific queued job**:
  ```bash
  python3 cli.py apply --job-id <job_id>
  ```

* **Bulk auto-apply to high-matching jobs (≥80%)**:
  ```bash
  python3 cli.py auto --min-score 80
  ```
