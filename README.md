# JobPing

JobPing helps job seekers discover roles that match their preferences, stay notified when new postings appear, and keep track of applications—all in one place.

## What it does

- **Account & auth** — Sign up and sign in with email/password or OAuth (e.g. Google, Outlook, Yahoo). Invalid login attempts are rejected.
- **Profile & resume** — Set preferred companies, roles, and locations; upload or replace a resume. Update preferences anytime.
- **Job discovery** — The system fetches listings aligned with preferred roles, refreshes on a **24-hour** cadence, **prioritizes** user-chosen companies, and **includes** a predefined company pool. Stale or unavailable listings are pruned (including postings older than **90 days**).
- **Recommendations** — At least one preferred role is required. Recommendations use preferences plus resume text when available; preference-only mode works without a resume. Jobs can be shown **sorted by similarity** to the user’s profile.
- **Notifications** — Alerts for new matching jobs (role and company), reminders for jobs not yet applied to, and confirmations when profile or resume changes.
- **Jobs in the app** — View title, company, salary, location, description, and a link to the company’s career page; open external postings from the app.
- **Engagement** — Mark jobs as applied or not applied, keep a full **recommendation history**, and use **favourites** (add/remove independently of application status).

## Tech stack

| Layer | Technology |
|--------|------------|
| Frontend | Vue 3, Vite, Vue Router, Pinia |
| Backend | Flask 3.x, Flask-JWT-Extended |
| Database | PostgreSQL 16.x + pgvector (planned) |
| Runtime | Python 3.12+ |

## Repository layout

```
JobPing/
├── backend/          # Flask API (blueprints: auth, profile, jobs)
│   ├── app/
│   ├── wsgi.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/         # Vue 3 SPA (dev server proxies /api → Flask)
└── README.md
```

## Prerequisites

Before you pull and run the project, install:

- **Python 3.12+** (3.12 matches our backend target)
- **Node.js** current LTS and **npm** (for the Vue/Vite app)
- **Git**

Confirm versions:

```bash
python3 --version
node --version
npm --version
```

## First-time setup (after `git clone` / `git pull`)

### 1. Backend

```bash
cd backend
python3 -m venv .venv
```

**macOS / Linux**

```bash
source .venv/bin/activate
```

**Windows (PowerShell)**

```powershell
.venv\Scripts\Activate.ps1
```

Then install dependencies and configure the environment:

```bash
pip install -r requirements.txt
cp .env.example .env
```

Edit `backend/.env` if you need non-default secrets locally. **Do not commit `.env`**; it is gitignored.

### 2. Frontend

From the repository root:

```bash
cd frontend
npm install
```

## Running locally for development

You need **both** servers running: Flask serves the JSON API; Vite serves the UI and **proxies** browser requests from `/api` to Flask (see `frontend/vite.config.js`).

**Terminal 1 — API (default [http://127.0.0.1:5000](http://127.0.0.1:5000))**

```bash
cd backend
source .venv/bin/activate   # or Windows activate script above
export FLASK_APP=wsgi:app
flask run
```

On **Windows (cmd.exe)**: `set FLASK_APP=wsgi:app` then `flask run`.  
On **Windows (PowerShell)**: `$env:FLASK_APP = "wsgi:app"` then `flask run`.

**Terminal 2 — frontend (Vite default [http://127.0.0.1:5173](http://127.0.0.1:5173))**

```bash
cd frontend
npm run dev
```

Open the **Vite URL** in the browser so API calls use the dev proxy. A quick API check (with Flask running):

```bash
curl http://127.0.0.1:5000/api/health
```

Expected: `{"status":"ok"}`.

## Working with the team on Git

1. **Pull before you start** so you have the latest `main` (or your shared integration branch):

   ```bash
   git pull origin main
   ```

2. **Use feature branches** for your work (`feature/your-topic`) and open pull requests when the team agrees on that workflow.

3. **After pulling**, if dependencies changed, re-run `pip install -r backend/requirements.txt` and/or `npm install` in `frontend/`.

4. Never commit secrets, virtualenvs (`.venv/`), or `frontend/node_modules/` — they are covered by `.gitignore`.

## License

To be determined.
