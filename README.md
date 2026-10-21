# MarketMind AI

> **Instant market intelligence for founders.** Enter any market topic — two AI agents research the web in real time and deliver a consultant-grade strategic report in under 5 minutes.

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![CrewAI](https://img.shields.io/badge/CrewAI-0.102-6366f1?logo=openai&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ecf8e?logo=supabase&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## What It Does

MarketMind AI is a full-stack SaaS application that automates market research using a **multi-agent AI pipeline**:

1. A **Market Researcher agent** searches the live web — pulling competitor data, funding rounds, customer reviews, and market sizing with cited sources.
2. A **Business Strategist agent** transforms the raw research into a structured, decision-ready report.

Every report includes **9 sections**: Executive Summary, Opportunity Score, Competitive Landscape, Customer Pain Points, Recommended Positioning, Go-To-Market Strategy, Risk Register, 30-Day Quick Wins, and a 90-Day Action Plan.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **AI Agents** | [CrewAI](https://crewai.com) + [Groq Llama 3.3 70B](https://console.groq.com) |
| **Web Search** | [Serper.dev](https://serper.dev) (real-time Google search) |
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **Database / Auth** | [Supabase](https://supabase.com) (PostgreSQL + Row-Level Security + JWT auth) |
| **PDF Export** | PyMuPDF (`fitz.Story` — multi-page A4) |
| **Frontend** | Vanilla JS, HTML/CSS (no framework) |
| **Auth** | Supabase Auth (email + password) |

---

## Features

- **Async job queue** — submit a topic, come back when done. No frozen browser tabs.
- **Live job polling** — progress shown in real time; state survives page refresh.
- **PDF export** — styled, multi-page A4 PDF download for every report.
- **Public share links** — generate a shareable URL for any report (no login required to view).
- **Usage tracking** — free tier enforced at 5 reports/month with a billing upgrade UI.
- **Crash recovery** — stale `running` jobs are automatically reset to `failed` on server restart.

---

## Project Structure

```
ai-saas/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app — all routes
│   │   ├── crew_logic.py    # CrewAI agents & tasks
│   │   ├── database.py      # Supabase repository (all DB operations)
│   │   ├── pdf_export.py    # Markdown → multi-page PDF via PyMuPDF Story
│   │   ├── auth.py          # JWT verification (Supabase)
│   │   ├── schemas.py       # Pydantic request/response models
│   │   └── config.py        # Settings (pydantic-settings, .env)
│   ├── supabase_schema.sql  # Full DB schema — run once in Supabase SQL editor
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── index.html           # Entry point — redirects to landing
    ├── landing.html         # Marketing page (auth modal, pricing)
    ├── app.html             # Dashboard shell (sidebar, pages, modals)
    ├── app.js               # All dashboard logic (jobs, reports, polling)
    ├── share.html           # Public report viewer (no login)
    └── style.css            # Design system (tokens, components)
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- A [Supabase](https://supabase.com) project (free tier is fine)
- A [Groq](https://console.groq.com/keys) API key (free)
- A [Serper.dev](https://serper.dev) API key (free tier — 2,500 searches/month)

---

### 1. Clone the repo

```bash
git clone https://github.com/your-username/ai-saas.git
cd ai-saas
```

### 2. Set up the database

1. Create a new project at [supabase.com](https://supabase.com).
2. Open the **SQL Editor** and run the entire contents of `backend/supabase_schema.sql`.
3. From **Project Settings → API**, copy:
   - Project URL
   - `anon` public key
   - `service_role` secret key

### 3. Configure environment variables

```bash
cd backend
cp .env.example .env
```

Edit `.env`:

```env
# Server
APP_ENV=development
APP_BASE_URL=http://127.0.0.1:5500
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:5500

# LLM — https://console.groq.com/keys
GROQ_API_KEY=gsk_...
GROQ_MODEL_NAME=groq/llama-3.3-70b-versatile

# Web search — https://serper.dev
SERPER_API_KEY=...

# Supabase
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_ANON_KEY=eyJ...
```

### 4. Install dependencies and start the backend

```bash
# From the backend/ directory
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python -m app.main
```

The API is now running at **http://localhost:8000**.  
Interactive docs: **http://localhost:8000/docs**

### 5. Open the frontend

Serve the `frontend/` folder with any static file server. The easiest options:

```bash
# Python (from the frontend/ directory)
python -m http.server 5500

# VS Code — install the "Live Server" extension and click "Go Live"

# Node.js
npx serve frontend
```

Then open **http://127.0.0.1:5500** in your browser.

> Make sure `APP_BASE_URL` and `CORS_ORIGINS` in your `.env` match the address you're serving the frontend from.

---

## API Reference

All authenticated endpoints require a Supabase JWT in the `Authorization` header:

```
Authorization: Bearer <supabase_access_token>
```

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/health` | — | Health check |
| `POST` | `/api/v1/auth/signup` | — | Create a new account |
| `POST` | `/api/v1/jobs` | ✓ | Submit a new analysis job |
| `GET` | `/api/v1/jobs` | ✓ | List all jobs for the user |
| `GET` | `/api/v1/jobs/{job_id}` | ✓ | Poll job status |
| `GET` | `/api/v1/reports` | ✓ | List all completed reports |
| `GET` | `/api/v1/reports/{id}` | ✓ | Get a full report |
| `GET` | `/api/v1/reports/{id}/pdf` | ✓ | Download report as PDF |
| `POST` | `/api/v1/reports/{id}/share` | ✓ | Create a public share link |
| `GET` | `/api/v1/share/{token}` | — | View a shared report (public) |
| `GET` | `/api/v1/usage` | ✓ | Get usage and plan info |

Full interactive docs available at `/docs` when `APP_ENV=development`.

---

## Database Schema

Four tables in Supabase (all with Row-Level Security enabled):

| Table | Purpose |
|---|---|
| `analysis_reports` | Completed report content, keyed by `client_id` |
| `jobs` | Async job queue — tracks status (`queued → running → done/failed`) |
| `usage_events` | Per-user monthly usage counter |
| `share_tokens` | Random tokens for public report sharing |

Run `backend/supabase_schema.sql` in the Supabase SQL Editor to create everything.

---

## How the AI Pipeline Works

```
User submits topic
        │
        ▼
FastAPI creates a job (status: queued)
        │
        ▼  (BackgroundTasks — non-blocking)
┌─────────────────────────────────────────┐
│  CrewAI Sequential Pipeline             │
│                                         │
│  1. Market Researcher Agent             │
│     • Searches web via Serper.dev       │
│     • Gathers: TAM/SAM/SOM, competitors │
│       funding rounds, customer reviews  │
│     • Labels data [PRIMARY/SECONDARY]   │
│                                         │
│  2. Business Strategist Agent           │
│     • Reads researcher output           │
│     • Writes 9-section markdown report  │
│     • Scores GTM channels (1–5)         │
│     • Builds risk register & 90-day plan│
└─────────────────────────────────────────┘
        │
        ▼
Report saved to Supabase → job status: done
        │
        ▼
Frontend polls /jobs/{id} every 5s → notifies user
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `APP_ENV` | No | `development` or `production` (default: `development`) |
| `APP_BASE_URL` | Yes | Base URL for share links (e.g. `http://127.0.0.1:5500`) |
| `CORS_ORIGINS` | Yes | Comma-separated allowed origins |
| `GROQ_API_KEY` | Yes | Groq API key |
| `GROQ_MODEL_NAME` | No | Default: `groq/llama-3.3-70b-versatile` |
| `SERPER_API_KEY` | Yes | Serper.dev API key for web search |
| `SUPABASE_URL` | Yes | Your Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Service role key (server-side only, never expose) |
| `SUPABASE_ANON_KEY` | Yes | Anon/public key (safe for frontend) |

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m 'feat: add your feature'`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">Built with CrewAI · Groq · FastAPI · Supabase</p>
