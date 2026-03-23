import os
from datetime import date

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

from agents.market_intelligence import expand_companies, get_company_pulse
from core.watchlist import add_company, list_companies, remove_company, save_pulse, load_pulse, migrate_watchlist
from agents.wellbeing import (
    get_encouragement_on_log, get_reframe_on_hard_status,
    get_one_thing_today, get_on_demand_encouragement,
)
from agents.resume_tailor import tailor_cv
from core.cv_store import get_cv_as_text
from core.pdf_renderer import render_resume_pdf
from core.tracker import (
    init_db, add_application, get_application, list_applications,
    update_status, update_application, delete_application,
    get_application_counts_by_date, ApplicationIn, ApplicationUpdate,
)

load_dotenv()

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
    add_application(DB_PATH, new_app)
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
async def watchlist_add(request: Request, company_name: str = Form(...)):
    """Add a company to the watchlist and return updated watchlist partial."""
    try:
        add_company(DB_PATH, company_name)
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


@app.post("/companies/{company_id}/delete")
async def company_delete(company_id: int):
    """Remove a company from the watchlist."""
    remove_company(DB_PATH, company_id)
    return RedirectResponse("/intelligence", status_code=303)


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
    return templates.TemplateResponse(
        request,
        "partials/resume_result.html",
        {
            "filename": filename,
            "target_role": tailored.target_role,
            "target_company": tailored.target_company,
        },
    )


@app.get("/resume/download/{filename}")
async def resume_download(filename: str):
    """Serve a generated resume PDF for download."""
    file_path = os.path.join(RESUMES_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Resume not found")
    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename=filename,
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
# Delete application
# ---------------------------------------------------------------------------

@app.post("/applications/{application_id}/delete")
async def applications_delete(application_id: int):
    """Delete an application."""
    delete_application(DB_PATH, application_id)
    return RedirectResponse("/applications", status_code=303)
