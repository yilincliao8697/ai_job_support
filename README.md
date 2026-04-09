# AI Job Hunting Platform

A personal AI-powered job hunting platform that runs entirely on your own machine. Point it at a job description and it tailors your resume, writes a cover letter, and tracks the application — all in one flow. Additional tools to help with company research, creating LinkedIn posts, and on-demand encouragement included.

**Try it in 30 seconds** → [Getting started (Docker)](#getting-started-docker)

---

### What you get

**Core flow**

| | |
|---|---|
| **Guided apply pipeline** | Paste a JD → tailored resume → cover letter → tracked application, step by step |
| **Resume tailor** | Claude rewrites your CV to mirror JD language and renders a polished PDF |
| **Cover letter generator** | 3-paragraph letter in your chosen tone, saved to history |
| **Application tracker** | Full CRUD with AI encouragement on log and reframes on rejection |

**Side tools**

| | |
|---|---|
| **Role fit suggestions** | AI reads your master CV and surfaces roles you may not have considered |
| **Company research** | Paste a JD → similar companies + live Company Pulse (funding, headcount, open roles) |
| **LinkedIn post drafts** | Three post options per generation; regenerate individual slots |
| **Wellbeing layer** | On-demand encouragement, contextual to what you're going through |

---

Uses production agentic LLM patterns throughout: multi-model routing, live web search tool use, structured output extraction, and iterative human-in-the-loop revision workflows.

Built with FastAPI + HTMX for a calm, focused UX. No feeds, no notifications — everything on demand.

---

## Features

### Guided Apply Pipeline
Step-by-step flow that walks you through a full application: paste the JD → review your CV → generate a tailored resume → generate a cover letter (optional) → record the application. Progress is tracked with a stepper UI; you can navigate back freely without losing completed stages.

### Resume Tailor
Paste a job description → Claude (`claude-sonnet-4-6`) selects relevant experience, rewrites bullet points to mirror JD language, and renders a polished PDF.

- **Iterative revision loop** — submit feedback after reviewing; each round accumulates a revision context summary (via Haiku) that carries forward to subsequent Sonnet calls
- **Live edit mode** — edit any section inline after generation and re-render the PDF without an LLM call
- **Resume history** — full revision chain stored in SQLite; revisit and branch any prior version

### Cover Letter Generator
Paste a JD → Claude writes a tailored 3-paragraph cover letter in your chosen tone (professional, warm, enthusiastic). Add a personal note for extra context. Saved to history.

### Master CV Editor
Edit your source CV as YAML directly in the browser (CodeMirror editor), or upload an existing PDF and Claude extracts it into the YAML schema automatically.

### Market Intelligence
Paste a JD → Claude expands it into 5–10 similar companies you may have missed. Click any company on your watchlist to fetch a structured **Company Pulse**:

- Recent funding, headcount direction, layoff news, open roles
- Powered by Claude's `web_search` tool with a multi-turn loop to handle tool-use-only stop reasons
- Pulse results cached in SQLite; refresh on demand

### LinkedIn Post Generator
Pick a category (project, insight, learning, etc.) and tone → Claude drafts three post options. Paste a source URL and Claude summarises it into the post. Regenerate individual slots without losing the others.

### Application Tracker
Full CRUD for job applications with status tracking. Contextual AI moments are woven in:
- **Encouragement on log** — warm, specific message generated on each new application
- **Reframe on rejection** — grounded perspective when marking an application as rejected or ghosted

### Wellbeing Layer
On-demand encouragement page. Accepts free-text input for contextual responses, or delivers a general supportive message. Deliberately not intrusive — one page, on your terms.

### Role Fit
AI reads your master CV and suggests 6–8 roles you could target, grouped by fit level: **Strong match** (direct experience), **Adjacent fit** (transferable angle), and **Stretch** (aspirational but evidenced). Each suggestion is grounded in specific CV entries — not generic reasoning. Results are cached; refresh when your CV changes.

### Dashboard
Effort chart (applications by date), "one thing today" AI suggestion, and nav cards for all modules.

---

## How It Works

The interesting engineering is in the agents layer:

| Pattern | Where |
|---|---|
| **Tool use / web search** | `agents/market_intelligence.py` — Claude calls `web_search` to gather live company data, handles multi-turn tool loops |
| **Structured output extraction** | Both agent modules: Claude returns typed JSON; the app validates schema and deserializes into dataclasses |
| **Multi-model routing** | Sonnet for quality-sensitive tasks (resume, company pulse); Haiku for short, latency-sensitive outputs (encouragement, feedback summarization) |
| **Iterative revision with accumulated context** | Resume tailor chains multiple feedback rounds into a numbered revision brief, passed back to Claude on each call |
| **Prompt engineering** | Role assignment, explicit output schemas, and instruction blocks in every system prompt |

---

## Getting started (Docker)

**Requirements:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (free, Mac / Windows / Linux)

**1. Run the app**

```bash
docker run -p 8000:8000 -v ~/my-job-data:/mnt/data ghcr.io/yilincliao8697/ai-job-support:latest
```

Your data (database, resumes, CV) is stored in `~/my-job-data` on your own machine and persists across restarts.

**2. Open the app**

Go to **http://localhost:8000**

**3. Add your API key**

Go to **Settings** and paste your [Anthropic API key](https://console.anthropic.com/). It's stored locally in your database — it never leaves your machine.

> **Cost note:** AI features call the Anthropic API, which charges per token. Normal usage (a few resumes and company lookups a day) costs cents. You can monitor usage in the [Anthropic console](https://console.anthropic.com/).

That's it. No accounts, no subscription, no configuration files.

**Alternative: docker-compose**

Download [`docker-compose.yml`](docker-compose.yml) to a folder, then:

```bash
docker-compose up -d
```

---

## Development setup

**Prerequisites:** Python 3.11+

```bash
git clone https://github.com/yilincliao8697/ai-job-support
cd ai-job-support

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp data/master_cv.example.yaml data/master_cv.yaml

uvicorn web.main:app --reload
```

Open `http://localhost:8000`, then go to **Settings** to add your Anthropic API key.

Alternatively, set it via a `.env` file:

```bash
ANTHROPIC_API_KEY=your_key_here
```

---

## Architecture

```
ai_job_support/
├── agents/
│   ├── market_intelligence.py   # Company Expander + Pulse (Sonnet + web_search tool)
│   ├── resume_tailor.py         # CV tailoring + feedback summarisation (Sonnet + Haiku)
│   ├── cover_letter.py          # Cover letter generation (Sonnet)
│   ├── role_suggester.py        # Role fit suggestions from master CV (Sonnet)
│   ├── linkedin_post.py         # LinkedIn post drafting (Sonnet)
│   ├── cv_from_pdf.py           # PDF text extraction → YAML (Sonnet)
│   └── wellbeing.py             # Encouragement + reframes (Haiku)
├── core/
│   ├── cv_store.py              # Load/parse master_cv.yaml
│   ├── tracker.py               # SQLite CRUD for applications
│   ├── resume_store.py          # Resume history + revision chain
│   ├── cover_letter_store.py    # Cover letter history
│   ├── pipeline_store.py        # Guided apply pipeline state
│   ├── settings_store.py        # App settings (API key storage)
│   ├── pdf_renderer.py          # Jinja2 → HTML → WeasyPrint → PDF
│   └── watchlist.py             # Target companies CRUD
├── web/
│   ├── main.py                  # FastAPI app + all routes
│   ├── templates/               # Jinja2 HTML (HTMX partials)
│   └── static/                  # CSS, minimal JS
├── resume_templates/
│   └── default.html.j2          # Resume visual design
├── data/
│   ├── master_cv.yaml           # Your career data (gitignored)
│   ├── master_cv.example.yaml   # Template / placeholder
│   ├── resumes/                 # Generated PDFs (gitignored)
│   └── jobs.db                  # SQLite (gitignored)
└── tests/                       # Pytest suite
```

**Frontend:** HTMX handles all dynamic updates (partial swaps, indicators, inline forms) with no custom JavaScript framework. The server renders HTML partials directly.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Web framework | FastAPI |
| Frontend | HTMX + Jinja2 |
| AI — quality tasks | `claude-sonnet-4-6` |
| AI — speed tasks | `claude-haiku-4-5-20251001` |
| PDF generation | WeasyPrint |
| Database | SQLite (no ORM) |

---

## Implementation Notes

**Model routing rationale:** Sonnet is used where output quality directly affects user decisions (resume copy, company research synthesis). Haiku handles high-frequency, short-output tasks where latency and cost matter more — encouragement messages fire on every application log, and feedback summarisation is a preprocessing step within a larger flow.

**Revision context accumulation:** Each revision round summarises raw feedback into 1–2 sentences (Haiku call), then appends it to a numbered revision brief. The full brief is injected into the next Sonnet prompt. This gives Claude cumulative context across multiple feedback rounds without blowing up token counts.

**Tool use loop handling:** The web search agent handles the case where Claude's `stop_reason` is `end_turn` after tool calls but before emitting a text block — it sends the tool results back and explicitly prompts for the final JSON synthesis, making the multi-turn loop robust.

**Structured output:** Both agents use explicit JSON schemas in the prompt and validate required fields on parse. Markdown code fence stripping handles model responses that wrap JSON in ` ```json ` blocks.

---

## Data & privacy

Everything runs locally. Your CV, resumes, applications, and API key are stored in a SQLite database and local files on your own machine (or Docker volume). Nothing is sent to any server except Anthropic's API when you use AI features.

---

## Environment variables

All optional — API key can be set via the Settings page instead.

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Overrides the in-app key if set |
| `DB_PATH` | `data/jobs.db` | SQLite path |
| `CV_PATH` | `data/master_cv.yaml` | Master CV path |
| `RESUMES_DIR` | `data/resumes` | PDF output directory |

---

## Running Tests

```bash
pytest tests/
```

---

## Routes

| Route | Description |
|---|---|
| `/` | Dashboard |
| `/apply/start` | Start the guided apply pipeline |
| `/applications` | Application tracker (includes in-progress pipelines) |
| `/resume` | Generate a tailored resume PDF |
| `/resume/history` | Resume history + revision tree |
| `/resume/:id/edit` | Live edit a generated resume |
| `/cover-letter` | Generate a cover letter |
| `/cover-letter/history` | Saved cover letters |
| `/cv/edit` | Edit master CV as YAML or upload a PDF |
| `/intelligence` | Company Expander — paste a JD, get similar companies |
| `/companies` | Watchlist browser grouped by sector |
| `/companies/:id` | Company Pulse view |
| `/roles` | Role Fit — AI suggests target roles from your master CV |
| `/linkedin` | LinkedIn post generator |
| `/encouragement` | On-demand wellbeing support |
| `/settings` | API key and app settings |
