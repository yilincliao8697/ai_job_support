import dataclasses
import io
import itertools
import json
import os
import re as _re
import yaml
from datetime import date
from urllib.parse import quote, unquote

from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

from agents.cv_from_pdf import extract_pdf_text, cv_yaml_from_pdf
from agents.linkedin_post import (
    CATEGORIES,
    TONES,
    get_linkedin_context,
    fetch_url_content,
    generate_linkedin_posts,
    regenerate_linkedin_post,
)
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
    toggle_resume_star,
)
from agents.cover_letter import TONES as COVER_LETTER_TONES, generate_cover_letter
from core.cover_letter_store import (
    init_cover_letters_table, save_cover_letter, list_cover_letters,
    get_cover_letter, delete_cover_letter,
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
init_cover_letters_table(DB_PATH)

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
    flash = unquote(request.cookies.get("flash_encouragement", ""))
    applications = list_applications(DB_PATH, active_only=active_only)
    response = templates.TemplateResponse(
        request,
        "applications/list.html",
        {"applications": applications, "show_all": not active_only, "flash_encouragement": flash},
    )
    if flash:
        response.delete_cookie("flash_encouragement")
    return response


@app.get("/applications/new")
async def applications_new_form(
    request: Request,
    company: str = "",
    role: str = "",
    resume: str = "",
    resume_id: int = 0,
):
    """Render new application form, optionally pre-filled from query params."""
    resume_record = get_resume(DB_PATH, resume_id) if resume_id else None
    if resume_record:
        company = resume_record.company
        role = resume_record.role
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
            "resume_record": resume_record,
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
    response = RedirectResponse("/applications", status_code=303)
    response.set_cookie("flash_encouragement", quote(encouragement), max_age=60, httponly=True)
    return response


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
            "resume_record": None,
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
        headers={
            "Content-Disposition": f'inline; filename="{safe_name}"',
            "Cache-Control": "no-store",
        },
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


@app.post("/resume/history/{resume_id}/star")
async def resume_history_star(resume_id: int):
    """Toggle star from history page. Returns replacement star button only."""
    from fastapi.responses import HTMLResponse
    new_val = toggle_resume_star(DB_PATH, resume_id)
    label = "★" if new_val else "☆"
    html = (
        f'<button class="btn btn-secondary"'
        f' style="font-size: 0.8rem; padding: 0.25rem 0.6rem;"'
        f' hx-post="/resume/history/{resume_id}/star"'
        f' hx-target="this"'
        f' hx-swap="outerHTML">{label}</button>'
    )
    return HTMLResponse(html)


@app.post("/resume/{resume_id}/star")
async def resume_star(resume_id: int):
    """Toggle star from edit page. Returns replacement star-toggle div."""
    from fastapi.responses import HTMLResponse
    new_val = toggle_resume_star(DB_PATH, resume_id)
    label = "★ Starred" if new_val else "☆ Star"
    html = (
        f'<div id="star-toggle">'
        f'<button class="btn btn-secondary"'
        f' hx-post="/resume/{resume_id}/star"'
        f' hx-target="#star-toggle"'
        f' hx-swap="outerHTML">{label}</button>'
        f'</div>'
    )
    return HTMLResponse(html)


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
        "website": form.get("website", ""),
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

    awards = []
    for i in itertools.count():
        if f"award_{i}_title" not in form:
            break
        awards.append({
            "title": form[f"award_{i}_title"],
            "issuer": form.get(f"award_{i}_issuer", ""),
            "date": form.get(f"award_{i}_date", ""),
            "description": form.get(f"award_{i}_description", ""),
        })

    education = []
    for i in itertools.count():
        if f"edu_{i}_institution" not in form:
            break
        education.append({
            "institution": form[f"edu_{i}_institution"],
            "degree": form.get(f"edu_{i}_degree", ""),
            "start": form.get(f"edu_{i}_start", ""),
            "end": form.get(f"edu_{i}_end", ""),
            "gpa": form.get(f"edu_{i}_gpa", ""),
        })

    try:
        font_size = float(form.get("font_size", 10.5))
        font_size = max(8.0, min(13.0, font_size))
    except ValueError:
        font_size = 10.5

    font_family = form.get("font_family", "Georgia, 'Times New Roman', serif")

    raw_order = form.get("section_order", "experience,projects,awards,education,skills")
    section_order = [s.strip() for s in raw_order.split(",") if s.strip()]

    return TailoredCV(
        personal=personal,
        experience=experience,
        projects=projects,
        education=education,
        skills=skills,
        target_role=form.get("target_role", ""),
        target_company=form.get("target_company", ""),
        awards=awards,
        font_size=font_size,
        font_family=font_family,
        section_order=section_order,
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
        {"record": record, "cv": cv, "cache_bust": int(_datetime.now().timestamp())},
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
# CV Editor
# ---------------------------------------------------------------------------

@app.get("/cv/edit")
async def cv_edit_page(request: Request, saved: int = 0):
    """Render the master CV editor with current YAML content."""
    with open(CV_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    cv_exists = bool(content.strip())
    return templates.TemplateResponse(
        request,
        "cv_edit.html",
        {"content": content, "saved": saved == 1, "error": None, "cv_exists": cv_exists},
    )


@app.post("/cv/upload-pdf")
async def cv_upload_pdf(request: Request, pdf: UploadFile = File(default=None)):
    """Convert an uploaded CV PDF to YAML and write to master_cv.yaml."""
    if pdf is None or not pdf.filename:
        return RedirectResponse("/cv/edit", status_code=303)

    file_bytes = await pdf.read()
    if not file_bytes:
        return RedirectResponse("/cv/edit", status_code=303)

    pdf_text = extract_pdf_text(file_bytes)
    if not pdf_text:
        with open(CV_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        return templates.TemplateResponse(
            request,
            "cv_edit.html",
            {
                "content": content,
                "saved": False,
                "error": "Could not extract text from PDF. Is it a text-based PDF (not scanned)?",
                "cv_exists": bool(content.strip()),
            },
        )

    with open("data/master_cv.example.yaml", "r", encoding="utf-8") as f:
        example_schema = f.read()

    yaml_str = cv_yaml_from_pdf(pdf_text, example_schema)

    try:
        yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        with open(CV_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        return templates.TemplateResponse(
            request,
            "cv_edit.html",
            {
                "content": content,
                "saved": False,
                "error": f"AI returned invalid YAML: {e}",
                "cv_exists": bool(content.strip()),
            },
        )

    with open(CV_PATH, "w", encoding="utf-8") as f:
        f.write(yaml_str)

    return RedirectResponse("/cv/edit?saved=1", status_code=303)


@app.post("/cv/save")
async def cv_save(request: Request, content: str = Form(...)):
    """Validate and write master CV YAML. Re-renders with error on invalid YAML."""
    try:
        yaml.safe_load(content)
    except yaml.YAMLError as e:
        return templates.TemplateResponse(
            request,
            "cv_edit.html",
            {"content": content, "saved": False, "error": str(e), "cv_exists": bool(content.strip())},
        )
    with open(CV_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    return RedirectResponse("/cv/edit?saved=1", status_code=303)


# ---------------------------------------------------------------------------
# LinkedIn Post Generator
# ---------------------------------------------------------------------------

@app.get("/linkedin")
async def linkedin_page(request: Request):
    """Render the LinkedIn post generator page."""
    return templates.TemplateResponse(
        request,
        "linkedin.html",
        {"categories": CATEGORIES, "tones": TONES},
    )


@app.post("/linkedin/generate")
async def linkedin_generate(
    request: Request,
    category: str = Form("tech_tool"),
    topic: str = Form(""),
    url: str = Form(""),
    tone: str = Form("insightful"),
):
    """Generate 3 LinkedIn post options. Returns the posts partial for HTMX swap."""
    cv_context = get_linkedin_context(CV_PATH)
    url_content = fetch_url_content(url) if url.strip() else ""
    posts = generate_linkedin_posts(cv_context, category, topic, tone, url_content)
    return templates.TemplateResponse(
        request,
        "partials/linkedin_posts.html",
        {"posts": posts, "category": category, "topic": topic, "url": url, "tone": tone},
    )


@app.post("/linkedin/regenerate")
async def linkedin_regenerate(
    request: Request,
    category: str = Form("tech_tool"),
    topic: str = Form(""),
    url: str = Form(""),
    tone: str = Form("insightful"),
    slot: int = Form(0),
):
    """Regenerate a single post slot. Returns one post slot partial for HTMX swap."""
    cv_context = get_linkedin_context(CV_PATH)
    url_content = fetch_url_content(url) if url.strip() else ""
    post = regenerate_linkedin_post(cv_context, category, topic, tone, url_content)
    return templates.TemplateResponse(
        request,
        "partials/linkedin_post_slot.html",
        {"post": post, "slot_index": slot, "category": category, "topic": topic, "url": url, "tone": tone},
    )


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
# Cover Letter
# ---------------------------------------------------------------------------

@app.get("/cover-letter")
async def cover_letter_page(request: Request):
    """Render the cover letter generator page."""
    return templates.TemplateResponse(
        request,
        "cover_letter.html",
        {"tones": COVER_LETTER_TONES},
    )


@app.post("/cover-letter/generate")
async def cover_letter_generate(
    request: Request,
    job_description: str = Form(...),
    tone: str = Form("professional"),
    job_title: str = Form(""),
    company: str = Form(""),
    personal_note: str = Form(""),
):
    """Generate a cover letter and save it. HTMX partial response."""
    cv_text = get_cv_as_text(CV_PATH)
    content = generate_cover_letter(
        job_description=job_description,
        cv_text=cv_text,
        tone=tone,
        personal_note=personal_note,
    )
    cover_letter_id = save_cover_letter(
        DB_PATH,
        content=content,
        tone=tone,
        job_title=job_title,
        company=company,
    )
    return templates.TemplateResponse(
        request,
        "partials/cover_letter_result.html",
        {"content": content, "cover_letter_id": cover_letter_id},
    )


@app.get("/cover-letter/history")
async def cover_letter_history_page(request: Request):
    """List all saved cover letters."""
    letters = list_cover_letters(DB_PATH)
    return templates.TemplateResponse(
        request,
        "cover_letter_history.html",
        {"letters": letters},
    )


@app.post("/cover-letter/history/{cover_letter_id}/delete")
async def cover_letter_delete(request: Request, cover_letter_id: int):
    """Delete a cover letter record. HTMX — removes the row from the table."""
    delete_cover_letter(DB_PATH, cover_letter_id)
    return ""


# ---------------------------------------------------------------------------
# Delete application
# ---------------------------------------------------------------------------

@app.post("/applications/{application_id}/delete")
async def applications_delete(application_id: int):
    """Delete an application."""
    delete_application(DB_PATH, application_id)
    return RedirectResponse("/applications", status_code=303)
