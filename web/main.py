import dataclasses
import itertools
import json
import os
import re as _re
from datetime import date

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

from agents.market_intelligence import expand_companies, get_company_pulse
from core.watchlist import (
    add_company, list_companies, list_companies_by_sector,
    remove_company, save_pulse, load_pulse, migrate_watchlist,
    update_company_details,
)
from agents.wellbeing import (
    get_encouragement_on_log, get_reframe_on_hard_status,
    get_one_thing_today, get_on_demand_encouragement,
)
from agents.resume_tailor import tailor_cv, summarise_feedback, TailoredCV
from core.cv_store import get_cv_as_text
from core.pdf_renderer import render_resume_pdf
from core.tracker import (
    init_db, add_application, get_application, list_applications,
    update_status, update_application, delete_application,
    get_application_counts_by_date, ApplicationIn, ApplicationUpdate,
)
from core.resume_store import (
    init_resumes_table, migrate_resumes, record_resume, link_application,
    list_resumes, delete_resume_record, get_resume, get_revision_chain,
    update_resume_json, update_resume_after_edit, get_tailored_cv,
)

load_dotenv()

from datetime import datetime as _datetime


def _format_date(value: str) -> str:
    """Jinja2 filter: format an ISO datetime string as 'Jan 15, 2025'."""
    if not value:
        return ""
    try:
        return _datetime.fromisoformat(value).strftime("%b %d, %Y")
    except (ValueError, TypeError):
        return value[:10]


DB_PATH = os.getenv("DB_PATH", "data/jobs.db")
CV_PATH = os.getenv("CV_PATH", "data/master_cv.yaml")
RESUMES_DIR = os.getenv("RESUMES_DIR", "data/resumes")
USER_BACKGROUND = os.getenv(
    "USER_BACKGROUND", "experienced ML engineer with Python and LLM background"
)

app = FastAPI()

app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

# Initialise DB on startup
init_db(DB_PATH)
migrate_watchlist(DB_PATH)
init_resumes_table(DB_PATH)
migrate_resumes(DB_PATH)

templates.env.filters["format_date"] = _format_date


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.get("/")
async def dashboard(request: Request):
    """Render the main dashboard with effort chart and module nav cards."""
    chart_data = get_application_counts_by_date(DB_PATH)
    all_apps = list_applications(DB_PATH, active_only=False)
    total = len(all_apps)
    first_date = chart_data[0]["date"] if chart_data else None

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "chart_data": chart_data,
            "total_applications": total,
            "first_application_date": first_date,
            "one_thing_today": get_one_thing_today(
                [vars(a) for a in list_applications(DB_PATH, active_only=True)],
                [],
            ),
        },
    )


# ---------------------------------------------------------------------------
# Application Tracker
# ---------------------------------------------------------------------------

@app.get("/applications")
async def applications_list(request: Request, show_all: int = 0):
    """List applications — active only by default."""
    active_only = show_all != 1
    applications = list_applications(DB_PATH, active_only=active_only)
    return templates.TemplateResponse(
        request,
        "applications/list.html",
        {"applications": applications, "show_all": not active_only},
    )


@app.get("/applications/new")
async def applications_new_form(
    request: Request,
    company: str = "",
    role: str = "",
    resume: str = "",
    resume_id: int = 0,
):
    """Render new application form, optionally pre-filled from query params."""
    return templates.TemplateResponse(
        request,
        "applications/form.html",
        {
            "app": None,
            "action": "/applications/new",
            "today": date.today().isoformat(),
            "prefill_company": company,
            "prefill_role": role,
            "prefill_resume": resume,
            "resume_id": resume_id,
        },
    )


@app.post("/applications/new")
async def applications_new_submit(
    request: Request,
    company: str = Form(...),
    role_title: str = Form(...),
    job_url: str = Form(""),
    date_applied: str = Form(...),
    status: str = Form(...),
    notes: str = Form(""),
    resume_filename: str = Form(""),
    referral_contacts: str = Form(""),
    resume_id: int = Form(0),
):
    """Create a new application."""
    new_app = ApplicationIn(
        company=company,
        role_title=role_title,
        job_url=job_url,
        date_applied=date_applied,
        status=status,
        notes=notes,
        resume_filename=resume_filename,
        referral_contacts=referral_contacts,
    )
    application_id = add_application(DB_PATH, new_app)
    if resume_id:
        link_application(DB_PATH, resume_id, application_id)
    encouragement = get_encouragement_on_log(company, role_title, USER_BACKGROUND)
    return templates.TemplateResponse(
        request,
        "applications/success.html",
        {"company": company, "role_title": role_title, "encouragement": encouragement},
    )


@app.get("/applications/{application_id}/edit")
async def applications_edit_form(request: Request, application_id: int):
    """Render edit form pre-filled with existing application data."""
    application = get_application(DB_PATH, application_id)
    if application is None:
        return templates.TemplateResponse(
            request, "404.html", {}, status_code=404
        )
    return templates.TemplateResponse(
        request,
        "applications/form.html",
        {
            "app": application,
            "action": f"/applications/{application_id}/edit",
            "today": date.today().isoformat(),
            "prefill_company": "",
            "prefill_role": "",
            "prefill_resume": "",
        },
    )


@app.post("/applications/{application_id}/edit")
async def applications_edit_submit(
    application_id: int,
    company: str = Form(...),
    role_title: str = Form(...),
    job_url: str = Form(""),
    date_applied: str = Form(...),
    status: str = Form(...),
    notes: str = Form(""),
    resume_filename: str = Form(""),
    referral_contacts: str = Form(""),
):
    """Apply edits to an application."""
    update_application(
        DB_PATH,
        application_id,
        ApplicationUpdate(
            company=company,
            role_title=role_title,
            job_url=job_url,
            date_applied=date_applied,
            status=status,
            notes=notes,
            resume_filename=resume_filename,
            referral_contacts=referral_contacts,
        ),
    )
    return RedirectResponse("/applications", status_code=303)


@app.post("/applications/{application_id}/status")
async def applications_update_status(
    request: Request,
    application_id: int,
    status: str = Form(...),
):
    """Update only the status of an application. Shows reframe for hard statuses."""
    update_status(DB_PATH, application_id, status)
    if status in ("rejected", "ghosted"):
        application = get_application(DB_PATH, application_id)
        reframe = get_reframe_on_hard_status(
            application.company, application.role_title, status
        )
        return templates.TemplateResponse(
            request,
            "applications/reframe.html",
            {"app": application, "status": status, "reframe": reframe},
        )
    return RedirectResponse("/applications", status_code=303)


# ---------------------------------------------------------------------------
# Market Intelligence
# ---------------------------------------------------------------------------

@app.get("/intelligence")
async def intelligence_page(request: Request):
    """Render the market intelligence page."""
    companies = list_companies(DB_PATH)
    return templates.TemplateResponse(
        request, "intelligence.html", {"companies": companies}
    )


@app.post("/intelligence/expand")
async def intelligence_expand(request: Request, job_description: str = Form(...)):
    """Expand a JD into similar companies and return HTMX partial."""
    companies = expand_companies(job_description)
    return templates.TemplateResponse(
        request, "partials/expander_results.html", {"companies": companies}
    )


@app.post("/intelligence/watchlist/add")
async def watchlist_add(
    request: Request,
    company_name: str = Form(...),
    sector: str = Form(""),
):
    """Add a company to the watchlist and return updated watchlist partial."""
    try:
        add_company(DB_PATH, company_name, sector=sector or None)
    except Exception:
        pass  # ignore duplicate inserts
    companies = list_companies(DB_PATH)
    return templates.TemplateResponse(
        request, "partials/watchlist.html", {"companies": companies}
    )


@app.get("/companies/{company_id}")
async def company_pulse_page(request: Request, company_id: int):
    """Render the Company Pulse page, loading cached pulse if available."""
    companies = list_companies(DB_PATH)
    company = next((c for c in companies if c.id == company_id), None)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    cached = load_pulse(DB_PATH, company_id)
    pulse = None
    if cached:
        from agents.market_intelligence import CompanyPulse
        pulse = CompanyPulse(**cached)
    return templates.TemplateResponse(
        request, "companies/pulse.html", {"company": company, "pulse": pulse}
    )


@app.post("/companies/{company_id}/pulse")
async def company_pulse_refresh(request: Request, company_id: int):
    """Fetch a fresh Company Pulse and return HTMX partial."""
    companies = list_companies(DB_PATH)
    company = next((c for c in companies if c.id == company_id), None)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    try:
        pulse = get_company_pulse(company.company_name)
        save_pulse(DB_PATH, company_id, pulse.__dict__)
        return templates.TemplateResponse(
            request, "partials/pulse_content.html", {"pulse": pulse}
        )
    except Exception as e:
        return f"<p class='text-muted'>Could not load pulse: {e}</p>"


@app.get("/companies")
async def companies_index(request: Request):
    """Browse all watchlist companies grouped by sector."""
    grouped = list_companies_by_sector(DB_PATH)
    return templates.TemplateResponse(
        request, "companies/index.html", {"grouped": grouped}
    )


@app.get("/companies/{company_id}/edit-form")
async def company_edit_form(request: Request, company_id: int):
    """Return the inline edit form partial for a company card."""
    companies = list_companies(DB_PATH)
    company = next((c for c in companies if c.id == company_id), None)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return templates.TemplateResponse(
        request, "companies/edit_form.html", {"company": company}
    )


@app.post("/companies/{company_id}/details")
async def company_update_details(
    request: Request,
    company_id: int,
    sector: str = Form(""),
    website_url: str = Form(""),
    careers_url: str = Form(""),
):
    """Update sector and URLs for a company. Returns the updated card partial."""
    update_company_details(
        DB_PATH,
        company_id,
        sector=sector or None,
        website_url=website_url or None,
        careers_url=careers_url or None,
    )
    companies = list_companies(DB_PATH)
    company = next((c for c in companies if c.id == company_id), None)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return templates.TemplateResponse(
        request, "companies/company_card.html", {"company": company}
    )


@app.get("/companies/{company_id}/card")
async def company_card(request: Request, company_id: int):
    """Return the company card partial (used to restore after cancel)."""
    companies = list_companies(DB_PATH)
    company = next((c for c in companies if c.id == company_id), None)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return templates.TemplateResponse(
        request, "companies/company_card.html", {"company": company}
    )


@app.post("/companies/{company_id}/delete")
async def company_delete(company_id: int):
    """Remove a company from the watchlist. Returns empty content for HTMX swap."""
    remove_company(DB_PATH, company_id)
    return ""


# ---------------------------------------------------------------------------
# Resume Tailor
# ---------------------------------------------------------------------------

@app.get("/resume")
async def resume_page(request: Request):
    """Render the resume tailor page."""
    return templates.TemplateResponse(request, "resume.html", {})


@app.post("/resume/generate")
async def resume_generate(request: Request, job_description: str = Form(...)):
    """Tailor the CV to the JD, render a PDF, and return an HTMX partial."""
    cv_text = get_cv_as_text(CV_PATH)
    tailored = tailor_cv(cv_text, job_description)
    filename = render_resume_pdf(tailored, RESUMES_DIR)
    tailored_json_str = json.dumps(dataclasses.asdict(tailored))
    resume_id = record_resume(
        DB_PATH, filename, tailored.target_company, tailored.target_role,
        job_description=job_description,
        tailored_json=tailored_json_str,
    )
    return templates.TemplateResponse(
        request,
        "partials/resume_result.html",
        {
            "filename": filename,
            "resume_id": resume_id,
            "target_role": tailored.target_role,
            "target_company": tailored.target_company,
        },
    )


@app.get("/resume/download/{filename}")
async def resume_download(filename: str):
    """Serve a generated resume PDF for download."""
    safe_name = os.path.basename(filename)
    if safe_name != filename or not safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename")
    file_path = os.path.join(RESUMES_DIR, safe_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Resume not found")
    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename=safe_name,
    )


@app.get("/resume/view/{filename}")
async def resume_view(filename: str):
    """Serve a generated resume PDF for inline browser preview (no download prompt)."""
    safe_name = os.path.basename(filename)
    if safe_name != filename or not safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename")
    file_path = os.path.join(RESUMES_DIR, safe_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Resume not found")
    return FileResponse(
        file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )


@app.get("/resume/history")
async def resume_history_page(request: Request):
    """Render the resume history page."""
    resumes = list_resumes(DB_PATH)
    return templates.TemplateResponse(
        request, "resume_history.html", {"resumes": resumes}
    )


@app.get("/resume/preview-frame/{filename}")
async def resume_preview_frame(request: Request, filename: str):
    """Return an iframe partial for inline PDF preview."""
    return templates.TemplateResponse(
        request, "partials/resume_preview_frame.html", {"filename": filename}
    )


@app.post("/resume/history/{resume_id}/delete")
async def resume_history_delete(request: Request, resume_id: int):
    """Delete a resume DB record (does not delete the PDF file). Returns updated history table body."""
    delete_resume_record(DB_PATH, resume_id)
    resumes = list_resumes(DB_PATH)
    return templates.TemplateResponse(
        request, "partials/resume_history_rows.html", {"resumes": resumes}
    )


def _build_revision_context(chain: list, new_summary: str) -> str:
    """Build a numbered revision context string from a chain of prior summaries plus the new one."""
    summaries = [r.feedback_summary for r in chain if r.feedback_summary]
    summaries.append(new_summary)
    return "\n".join(f"Round {i + 1}: {s}" for i, s in enumerate(summaries))


@app.post("/resume/revise")
async def resume_revise(
    request: Request,
    parent_resume_id: int = Form(...),
    feedback: str = Form(...),
):
    """Revise a previously generated resume based on user feedback. Returns updated result card partial."""
    parent = get_resume(DB_PATH, parent_resume_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    feedback_summary = summarise_feedback(feedback)
    chain = get_revision_chain(DB_PATH, parent_resume_id)
    revision_context = _build_revision_context(chain, feedback_summary)
    cv_text = get_cv_as_text(CV_PATH)
    tailored = tailor_cv(cv_text, parent.job_description, revision_context)
    filename = render_resume_pdf(tailored, RESUMES_DIR)
    tailored_json_str = json.dumps(dataclasses.asdict(tailored))
    resume_id = record_resume(
        DB_PATH, filename, tailored.target_company, tailored.target_role,
        job_description=parent.job_description,
        parent_id=parent_resume_id,
        feedback_summary=feedback_summary,
        tailored_json=tailored_json_str,
    )
    return templates.TemplateResponse(
        request,
        "partials/resume_result.html",
        {
            "filename": filename,
            "resume_id": resume_id,
            "target_role": tailored.target_role,
            "target_company": tailored.target_company,
        },
    )


@app.get("/resume/revise/{resume_id}")
async def resume_revise_page(request: Request, resume_id: int):
    """Render the dedicated revision page for a resume from history."""
    record = get_resume(DB_PATH, resume_id)
    if record is None or record.job_description is None:
        raise HTTPException(status_code=404, detail="Resume not found or predates revision support")
    chain = get_revision_chain(DB_PATH, resume_id)
    return templates.TemplateResponse(
        request,
        "resume_revise.html",
        {"record": record, "chain": chain},
    )


@app.post("/resume/revise-from-history")
async def resume_revise_from_history(
    request: Request,
    parent_resume_id: int = Form(...),
    job_description: str = Form(...),
    feedback: str = Form(...),
):
    """Revision triggered from the history page. Redirects to /resume/history on success."""
    parent = get_resume(DB_PATH, parent_resume_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    feedback_summary = summarise_feedback(feedback)
    chain = get_revision_chain(DB_PATH, parent_resume_id)
    revision_context = _build_revision_context(chain, feedback_summary)
    cv_text = get_cv_as_text(CV_PATH)
    tailored = tailor_cv(cv_text, job_description, revision_context)
    filename = render_resume_pdf(tailored, RESUMES_DIR)
    tailored_json_str = json.dumps(dataclasses.asdict(tailored))
    new_id = record_resume(
        DB_PATH, filename, tailored.target_company, tailored.target_role,
        job_description=job_description,
        parent_id=parent_resume_id,
        feedback_summary=feedback_summary,
        tailored_json=tailored_json_str,
    )
    return RedirectResponse(f"/resume/{new_id}/edit", status_code=303)


# ---------------------------------------------------------------------------
# Resume Live Edit
# ---------------------------------------------------------------------------

def _parse_resume_form(form: dict) -> TailoredCV:
    """Reconstruct a TailoredCV from indexed live-edit form fields."""
    personal = {
        "name": form.get("name", ""),
        "email": form.get("email", ""),
        "location": form.get("location", ""),
        "linkedin": form.get("linkedin", ""),
        "github": form.get("github", ""),
        "summary": form.get("summary", ""),
    }

    experience = []
    for i in itertools.count():
        if f"exp_{i}_company" not in form:
            break
        bullets = [
            form[k] for k in sorted(form)
            if _re.match(rf"exp_{i}_bullet_\d+$", k)
        ]
        experience.append({
            "company": form[f"exp_{i}_company"],
            "role": form[f"exp_{i}_role"],
            "start": form[f"exp_{i}_start"],
            "end": form[f"exp_{i}_end"],
            "bullets": [b for b in bullets if b.strip()],
        })

    projects = []
    for i in itertools.count():
        if f"proj_{i}_name" not in form:
            break
        bullets = [
            form[k] for k in sorted(form)
            if _re.match(rf"proj_{i}_bullet_\d+$", k)
        ]
        projects.append({
            "name": form[f"proj_{i}_name"],
            "description": form[f"proj_{i}_description"],
            "bullets": [b for b in bullets if b.strip()],
        })

    def _split(val: str) -> list[str]:
        return [s.strip() for s in val.split(",") if s.strip()]

    skills = {
        "languages": _split(form.get("languages", "")),
        "frameworks": _split(form.get("frameworks", "")),
        "tools": _split(form.get("tools", "")),
        "other": _split(form.get("other", "")),
    }

    education = json.loads(form.get("education_json", "[]"))

    return TailoredCV(
        personal=personal,
        experience=experience,
        projects=projects,
        education=education,
        skills=skills,
        target_role=form.get("target_role", ""),
        target_company=form.get("target_company", ""),
    )


@app.get("/resume/{resume_id}/edit")
async def resume_edit_page(request: Request, resume_id: int):
    """Render the live edit page for a generated resume."""
    record = get_resume(DB_PATH, resume_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    cv = get_tailored_cv(DB_PATH, resume_id)
    return templates.TemplateResponse(
        request,
        "resume_edit.html",
        {"record": record, "cv": cv},
    )


@app.post("/resume/{resume_id}/save")
async def resume_edit_save(request: Request, resume_id: int):
    """Save live edits: re-render PDF and update stored JSON. No LLM call."""
    record = get_resume(DB_PATH, resume_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    form = dict(await request.form())
    tailored = _parse_resume_form(form)
    filename = render_resume_pdf(tailored, RESUMES_DIR)
    tailored_json_str = json.dumps(dataclasses.asdict(tailored))
    update_resume_after_edit(DB_PATH, resume_id, tailored_json_str, filename)
    return RedirectResponse(f"/resume/{resume_id}/edit", status_code=303)


# ---------------------------------------------------------------------------
# Wellbeing / Encouragement
# ---------------------------------------------------------------------------

@app.get("/encouragement")
async def encouragement_page(request: Request):
    """Render the on-demand encouragement page with a default message."""
    default_message = get_on_demand_encouragement()
    return templates.TemplateResponse(
        request,
        "encouragement.html",
        {"default_message": default_message},
    )


@app.post("/encouragement")
async def encouragement_post(user_message: str = Form("")):
    """Return Claude's encouragement as an HTMX partial."""
    message = get_on_demand_encouragement(user_message)
    return f"<p style='margin:0; line-height:1.7;'>{message}</p>"


# ---------------------------------------------------------------------------
# Delete application
# ---------------------------------------------------------------------------

@app.post("/applications/{application_id}/delete")
async def applications_delete(application_id: int):
    """Delete an application."""
    delete_application(DB_PATH, application_id)
    return RedirectResponse("/applications", status_code=303)
