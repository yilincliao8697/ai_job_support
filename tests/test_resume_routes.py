import json
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from agents.resume_tailor import TailoredCV
from core.tracker import init_db


SAMPLE_TAILORED_CV = TailoredCV(
    personal={"name": "Jane Doe", "email": "jane@example.com", "location": "", "linkedin": "", "github": "", "summary": "ML engineer."},
    experience=[{"company": "Acme", "role": "ML Engineer", "start": "2023-01", "end": "present", "bullets": ["Built pipelines."]}],
    projects=[],
    education=[{"institution": "Uni", "degree": "BSc", "year": "2021"}],
    skills={"languages": ["Python"], "frameworks": [], "tools": [], "other": []},
    target_role="ML Engineer",
    target_company="Cohere",
)


@pytest.fixture(autouse=True)
def setup(monkeypatch, tmp_path):
    db = str(tmp_path / "test.db")
    resumes_dir = str(tmp_path / "resumes")
    cv_path = str(tmp_path / "cv.yaml")

    # Write a minimal CV file
    import yaml
    with open(cv_path, "w") as f:
        yaml.dump({"personal": {"name": "Jane"}, "experience": [], "projects": [], "education": [], "skills": {}}, f)

    monkeypatch.setenv("DB_PATH", db)
    monkeypatch.setenv("CV_PATH", cv_path)
    monkeypatch.setenv("RESUMES_DIR", resumes_dir)

    import importlib
    import web.main as main_module
    importlib.reload(main_module)
    init_db(db)
    monkeypatch.setattr(main_module, "DB_PATH", db)
    monkeypatch.setattr(main_module, "CV_PATH", cv_path)
    monkeypatch.setattr(main_module, "RESUMES_DIR", resumes_dir)

    return db, resumes_dir, main_module


def make_client(setup):
    _, _, main_module = setup
    return TestClient(main_module.app)


def _mock_claude_wellbeing(text="Keep going."):
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


@patch("agents.wellbeing._client")
def test_resume_page_returns_200(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    client = make_client(setup)
    response = client.get("/resume")
    assert response.status_code == 200


@patch("agents.resume_tailor._client")
@patch("agents.wellbeing._client")
def test_resume_generate_returns_download_link(mock_wc, mock_rc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()

    def _mock_tailor(*args, **kwargs):
        return SAMPLE_TAILORED_CV
    with patch("web.main.tailor_cv", side_effect=_mock_tailor), \
         patch("web.main.render_resume_pdf", return_value="cohere_2026-03-23.pdf"):
        _, _, main_module = setup
        client = TestClient(main_module.app)
        response = client.post("/resume/generate", data={"job_description": "ML Engineer at Cohere"})
    assert response.status_code == 200
    assert "cohere_2026-03-23.pdf" in response.text
    assert "/resume/download/" in response.text


@patch("agents.wellbeing._client")
def test_resume_download_serves_file(mock_wc, setup, tmp_path):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    _, resumes_dir, main_module = setup

    os.makedirs(resumes_dir, exist_ok=True)
    pdf_path = os.path.join(resumes_dir, "test_resume.pdf")
    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-1.4 test content")

    client = TestClient(main_module.app)
    response = client.get("/resume/download/test_resume.pdf")
    assert response.status_code == 200


@patch("agents.wellbeing._client")
def test_resume_download_404_for_missing(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    _, _, main_module = setup
    client = TestClient(main_module.app)
    response = client.get("/resume/download/nonexistent.pdf")
    assert response.status_code == 404


@patch("agents.wellbeing._client")
def test_applications_new_prefill_from_query_params(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    _, _, main_module = setup
    client = TestClient(main_module.app)
    response = client.get("/applications/new?company=Cohere&role=ML+Engineer&resume=cohere_2026.pdf")
    assert response.status_code == 200
    assert "Cohere" in response.text
    assert "ML Engineer" in response.text
