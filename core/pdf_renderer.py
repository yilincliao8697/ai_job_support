import os
import re
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from agents.resume_tailor import TailoredCV


TEMPLATE_DIR = Path("resume_templates")
TEMPLATE_FILE = "default.html.j2"


def _slugify(text: str) -> str:
    """Convert a company name to a filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s]+", "_", text)
    return text


def render_resume_pdf(tailored_cv: TailoredCV, output_dir: str) -> str:
    """
    Render a TailoredCV to a timestamped PDF file.

    Saves to output_dir/{company_slug}_{YYYY-MM-DD}.pdf.
    Returns the filename (not full path).
    """
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template(TEMPLATE_FILE)

    html_content = template.render(cv=tailored_cv)

    company_slug = _slugify(tailored_cv.target_company) or "company"
    today = date.today().isoformat()
    filename = f"{company_slug}_{today}.pdf"

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    HTML(string=html_content).write_pdf(str(output_path / filename))

    return filename
