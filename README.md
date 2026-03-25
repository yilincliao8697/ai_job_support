# AI Job Hunting Assistant

A personal AI-powered job hunting assistant demonstrating production agentic LLM patterns — multi-model routing, live web search tool use, structured output extraction, and iterative human-in-the-loop revision workflows.

Built with FastAPI + HTMX for a calm, focused UX. No feeds, no notifications — everything on demand.

---

## What This Demonstrates

This project was built as a portfolio piece for AI engineering roles. The interesting engineering is in the agents layer:

| Pattern | Where |
|---|---|
| **Tool use / web search** | `agents/market_intelligence.py` — Claude calls `web_search` to gather live company data, handles multi-turn tool loops |
| **Structured output extraction** | Both agent modules: Claude returns typed JSON; the app validates schema and deserializes into dataclasses |
| **Multi-model routing** | Sonnet for quality-sensitive tasks (resume, company pulse); Haiku for short, latency-sensitive outputs (encouragement, feedback summarization) |
| **Iterative revision with accumulated context** | Resume tailor chains multiple feedback rounds into a numbered revision brief, passed back to Claude on each call |
| **Prompt engineering** | Role assignment, explicit output schemas, and instruction blocks in every system prompt |

---

## Features

### Resume Tailor
Paste a job description → Claude (`claude-sonnet-4-6`) selects relevant experience, rewrites bullet points to mirror JD language, and renders a polished PDF.

- **Iterative revision loop** — submit feedback after reviewing; each round accumulates a revision context summary (via Haiku) that carries forward to subsequent Sonnet calls
- **Live edit mode** — edit any section inline after generation and re-render the PDF without an LLM call
- **Resume history** — full revision chain stored in SQLite; revisit and branch any prior version

### Market Intelligence
Paste a JD → Claude expands it into 5–10 similar companies you may have missed. Click any company on your watchlist to fetch a structured **Company Pulse**:

- Recent funding, headcount direction, layoff news, open roles
- Powered by Claude's `web_search` tool with a multi-turn loop to handle tool-use-only stop reasons
- Pulse results cached in SQLite; refresh on demand

### Application Tracker
Full CRUD for job applications with status tracking. Contextual AI moments are woven in:
- **Encouragement on log** — warm, specific message generated on each new application
- **Reframe on rejection** — grounded perspective when marking an application as rejected or ghosted

### Wellbeing Layer
On-demand encouragement page. Accepts free-text input for contextual responses, or delivers a general supportive message. Deliberately not intrusive — one page, on your terms.

### Dashboard
Effort chart (applications by date), "one thing today" AI suggestion, and nav cards for all modules.

---

## Architecture

```
ai_job_support/
├── agents/
│   ├── market_intelligence.py   # Company Expander + Pulse (Sonnet + web_search tool)
│   ├── resume_tailor.py         # CV tailoring + feedback summarisation (Sonnet + Haiku)
│   └── wellbeing.py             # Encouragement + reframes (Haiku)
├── core/
│   ├── cv_store.py              # Load/parse master_cv.yaml
│   ├── tracker.py               # SQLite CRUD for applications
│   ├── resume_store.py          # Resume history + revision chain
│   ├── pdf_renderer.py          # Jinja2 → HTML → WeasyPrint → PDF
│   └── watchlist.py             # Target companies CRUD
├── web/
│   ├── main.py                  # FastAPI app + all routes
│   ├── templates/               # Jinja2 HTML (HTMX partials)
│   └── static/                  # CSS, minimal JS
├── resume_templates/
│   └── default.html.j2          # Resume visual design
├── data/
│   ├── master_cv.yaml           # Your career data — edit directly
│   ├── target_companies.yaml    # Watchlist seed data
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

## Setup

**Prerequisites:** Python 3.11+, an Anthropic API key

```bash
git clone <repo-url>
cd ai_job_support

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file:

```bash
ANTHROPIC_API_KEY=your_key_here
```

Edit `data/master_cv.yaml` with your career history.

Run the app:

```bash
uvicorn web.main:app --reload
```

Open `http://localhost:8000`.

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
| `/intelligence` | Company Expander — paste a JD, get similar companies |
| `/companies` | Watchlist browser grouped by sector |
| `/companies/:id` | Company Pulse view |
| `/resume` | Generate a tailored resume PDF |
| `/resume/history` | Resume history + revision tree |
| `/resume/:id/edit` | Live edit a generated resume |
| `/applications` | Application tracker |
| `/encouragement` | On-demand wellbeing support |

---

## AI Engineering Notes

**Model routing rationale:** Sonnet is used where output quality directly affects user decisions (resume copy, company research synthesis). Haiku handles high-frequency, short-output tasks where latency and cost matter more — encouragement messages fire on every application log, and feedback summarisation is a preprocessing step within a larger flow.

**Revision context accumulation:** Each revision round summarises raw feedback into 1–2 sentences (Haiku call), then appends it to a numbered revision brief. The full brief is injected into the next Sonnet prompt. This gives Claude cumulative context across multiple feedback rounds without blowing up token counts.

**Tool use loop handling:** The web search agent handles the case where Claude's `stop_reason` is `end_turn` after tool calls but before emitting a text block — it sends the tool results back and explicitly prompts for the final JSON synthesis, making the multi-turn loop robust.

**Structured output:** Both agents use explicit JSON schemas in the prompt and validate required fields on parse. Markdown code fence stripping handles model responses that wrap JSON in ` ```json ` blocks.

---

## Deployment

Designed for Render or Railway with a persistent disk for SQLite and generated PDFs.

Environment variables:

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required |
| `DB_PATH` | `data/jobs.db` | SQLite path |
| `CV_PATH` | `data/master_cv.yaml` | Master CV path |
| `RESUMES_DIR` | `data/resumes` | PDF output directory |
| `USER_BACKGROUND` | `"experienced ML engineer..."` | Used in encouragement prompts |
