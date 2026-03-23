import os
import pytest
from datetime import date
from unittest.mock import patch
from agents.resume_tailor import TailoredCV
from core.pdf_renderer import render_resume_pdf, _slugify


SAMPLE_CV = TailoredCV(
    personal={"name": "Jane Doe", "email": "jane@example.com", "location": "London", "linkedin": "", "github": "", "summary": "ML engineer."},
    experience=[{"company": "Acme", "role": "ML Engineer", "start": "2023-01", "end": "present", "bullets": ["Built pipelines."]}],
    projects=[{"name": "LLM App", "description": "Demo.", "bullets": ["Used Claude API."]}],
    education=[{"institution": "University", "degree": "BSc CS", "year": "2021"}],
    skills={"languages": ["Python"], "frameworks": ["PyTorch"], "tools": ["Docker"], "other": []},
    target_role="ML Engineer",
    target_company="Cohere",
)


def test_slugify_lowercases_and_replaces_spaces():
    assert _slugify("Acme Corp") == "acme_corp"


def test_slugify_removes_special_chars():
    assert _slugify("Foo & Bar!") == "foo_bar"


def test_render_resume_pdf_creates_file(tmp_path):
    filename = render_resume_pdf(SAMPLE_CV, str(tmp_path))
    assert (tmp_path / filename).exists()


def test_render_resume_pdf_filename_format(tmp_path):
    filename = render_resume_pdf(SAMPLE_CV, str(tmp_path))
    today = date.today().isoformat()
    assert filename == f"cohere_{today}.pdf"


def test_render_resume_pdf_returns_filename_only(tmp_path):
    filename = render_resume_pdf(SAMPLE_CV, str(tmp_path))
    assert "/" not in filename
    assert filename.endswith(".pdf")


def test_render_resume_pdf_creates_output_dir(tmp_path):
    nested = str(tmp_path / "nested" / "dir")
    filename = render_resume_pdf(SAMPLE_CV, nested)
    assert os.path.exists(os.path.join(nested, filename))
