# CommitFlow 🚀
**AI-Powered GitHub Activity Automation & Authentic Habit Platform**

CommitFlow is a full-stack platform that transforms daily GitHub activity from artificial vanity metrics into **authentic, verified engineering progress**. It connects to your GitHub repositories, ingests existing code context, generates high-quality practice implementations, documentation, and unit tests using AI, verifies the changes against strict security guardrails, and opens automated Pull Requests.

---

## 🌟 Key Features

- **Anti-Spam / Verified Contributions Only:** No empty commits, whitespace tweaks, or fake activity. Every commit is validated code or documentation with test assertions.
- **Pull Request Default:** By default, changes are published to scoped branches (`automation/habit-{timestamp}`) with Pull Requests. Direct push is only allowed when explicitly opted-in.
- **Pluggable AI Adapters:** Built-in adapters for **OpenAI** (`gpt-4o`, `gpt-4o-mini`), **Anthropic** (`claude-3-5-sonnet`), and **Google Gemini** with strict JSON Schema output.
- **Security & Sandboxing:**
  - **Fernet Symmetric Encryption:** GitHub tokens and AI provider API keys are encrypted at rest.
  - **Path Boundary Guardrails:** Enforces `allowed_paths` whitelisting and eliminates directory traversal (`../`).
  - **Blacklist Filter:** Disallows modifications to `.env*`, `Dockerfile`, keys, secrets, `.git/`, and CI workflows.
  - **Secret Scanner:** Scans AI output for accidentally generated credentials before pushing to GitHub.
- **Distributed Scheduling with Zero Duplicate Commits:** Powered by **Celery Beat** and **Redis** with database-backed slot uniqueness constraints (`(automation_id, scheduled_slot)`).

---

## 🛠 Tech Stack

| Tier | Technology | Purpose |
| :--- | :--- | :--- |
| **Frontend** | Next.js 14, TypeScript, Tailwind CSS, Lucide Icons | Responsive dashboard, diff inspector, habit builder wizard |
| **Backend** | Django 5.x, Django REST Framework | Auth, models, REST APIs, business logic, cryptography |
| **Worker / Queue** | Celery 5.x, Redis 7.x, `django-celery-beat` | Distributed task execution, dynamic timezone scheduling |
| **Database** | PostgreSQL 16 (SQLite fallback for local dev) | Multi-tenant schema with UUIDv4 primary keys |
| **GitHub Access** | GitHub App / GitHub REST Data API | Granular contents & pull requests permissions |
| **AI Layer** | Python abstraction layer + Pydantic v2 schemas | Structured code proposals |

---

## 🚀 Quick Start

### Option A: Run with Docker Compose (Recommended)

1. Clone the repository and configure your environment:
   ```bash
   cp .env.example .env
   ```

2. Start the entire platform (PostgreSQL, Redis, Django, Celery Worker, Celery Beat, Next.js):
   ```bash
   docker compose -f docker/docker-compose.yml up --build
   ```

3. Open your browser:
   - **Frontend Dashboard:** [http://localhost:3000](http://localhost:3000)
   - **Backend REST API:** [http://localhost:8000/api/](http://localhost:8000/api/)
   - **Django Admin:** [http://localhost:8000/admin/](http://localhost:8000/admin/)

---

### Option B: Run Locally Without Docker

#### 1. Backend Setup
```bash
cd backend
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt

# Run migrations (uses SQLite if PostgreSQL is not active)
$env:USE_SQLITE="True"  # (PowerShell) or export USE_SQLITE=True
python manage.py migrate

# Run tests
python manage.py test tests

# Start Django development server
python manage.py runserver 0.0.0.0:8000
```

#### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000) to access the interactive dashboard.

---

## 📁 Repository Structure

```
CommitFlow/
├── backend/
│   ├── apps/
│   │   ├── authentication/       # Custom UUID User model, register/login APIs
│   │   ├── github_integration/   # GitHub App, installations, repository models
│   │   ├── ai_engine/            # AI provider adapters (OpenAI, Anthropic, Gemini)
│   │   ├── automations/          # Habit goals, schedules, CRUD APIs
│   │   ├── executions/           # Celery tasks, execution history, diff records
│   │   ├── validation/           # Path boundary, secret scanner, diff checker
│   │   └── git_publishing/       # GitHub Git Data API (trees, commits, PRs)
│   ├── commitflow/               # Django settings, Celery, URLs, WSGI/ASGI
│   ├── tests/                    # Backend unit & integration test suite
│   ├── requirements.txt
│   └── manage.py
├── frontend/
│   ├── src/
│   │   ├── app/                  # Next.js App Router (layout, globals, dashboard)
│   │   ├── components/           # Header, MetricCards, DiffViewer, Modals
│   │   ├── lib/                  # API client with offline fallback support
│   │   └── types/                # TypeScript interface definitions
│   ├── package.json
│   └── tailwind.config.ts
├── docker/
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🧪 Testing

The backend includes comprehensive test coverage verifying:
- Secret encryption/decryption roundtrip and UI masking
- Path traversal rejection (`../../` escape attempts)
- Restricted file modification rejection (`.env*`, workflows, etc.)
- Allowed path boundary verification
- Complete Celery execution task pipeline from context to simulated Git PR publication

Run the tests anytime:
```bash
cd backend
python manage.py test tests
```
