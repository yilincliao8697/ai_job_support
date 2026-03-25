import json
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from agents.resume_tailor import TailoredCV
from core.tracker import init_db
from core.resume_store import record_resume, get_resume


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


# ---------------------------------------------------------------------------
# /resume/view
# ---------------------------------------------------------------------------

@patch("agents.wellbeing._client")
def test_resume_view_returns_200_with_pdf_content_type(mock_wc, setup, tmp_path):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    _, resumes_dir, main_module = setup
    os.makedirs(resumes_dir, exist_ok=True)
    pdf_path = os.path.join(resumes_dir, "test_resume.pdf")
    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-1.4 test content")
    client = TestClient(main_module.app)
    response = client.get("/resume/view/test_resume.pdf")
    assert response.status_code == 200
    assert "application/pdf" in response.headers["content-type"]


@patch("agents.wellbeing._client")
def test_resume_view_content_disposition_is_inline(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    _, resumes_dir, main_module = setup
    os.makedirs(resumes_dir, exist_ok=True)
    with open(os.path.join(resumes_dir, "test_resume.pdf"), "wb") as f:
        f.write(b"%PDF-1.4 test content")
    client = TestClient(main_module.app)
    response = client.get("/resume/view/test_resume.pdf")
    assert "inline" in response.headers.get("content-disposition", "")


@patch("agents.wellbeing._client")
def test_resume_view_404_for_missing(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    client = make_client(setup)
    response = client.get("/resume/view/nonexistent.pdf")
    assert response.status_code == 404


@patch("agents.wellbeing._client")
def test_resume_view_rejects_path_traversal(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    client = make_client(setup)
    response = client.get("/resume/view/..%2F..%2Fetc%2Fpasswd")
    assert response.status_code in (400, 404)


# ---------------------------------------------------------------------------
# /resume/history
# ---------------------------------------------------------------------------

@patch("agents.wellbeing._client")
def test_resume_history_returns_200(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    client = make_client(setup)
    response = client.get("/resume/history")
    assert response.status_code == 200


@patch("agents.wellbeing._client")
def test_resume_history_renders_records(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    db, _, main_module = setup
    record_resume(db, "stripe_2026.pdf", "Stripe", "ML Engineer")
    record_resume(db, "cohere_2026.pdf", "Cohere", "AI Engineer")
    client = TestClient(main_module.app)
    response = client.get("/resume/history")
    assert response.status_code == 200
    assert "Stripe" in response.text
    assert "ML Engineer" in response.text
    assert "Cohere" in response.text


# ---------------------------------------------------------------------------
# /resume/preview-frame
# ---------------------------------------------------------------------------

@patch("agents.wellbeing._client")
def test_resume_preview_frame_returns_200_with_iframe(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    client = make_client(setup)
    response = client.get("/resume/preview-frame/test_resume.pdf")
    assert response.status_code == 200
    assert "<iframe" in response.text


# ---------------------------------------------------------------------------
# /resume/history/{id}/delete
# ---------------------------------------------------------------------------

@patch("agents.wellbeing._client")
def test_resume_history_delete_removes_record_and_returns_rows(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    db, _, main_module = setup
    resume_id = record_resume(db, "stripe_2026.pdf", "Stripe", "ML Engineer")
    client = TestClient(main_module.app)
    response = client.post(f"/resume/history/{resume_id}/delete")
    assert response.status_code == 200
    assert get_resume(db, resume_id) is None


# ---------------------------------------------------------------------------
# /resume/revise
# ---------------------------------------------------------------------------

def _mock_summarise(text="Emphasise LLM experience; shorten summary."):
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


@patch("web.main.summarise_feedback", return_value="Emphasise LLM experience; shorten summary.")
@patch("web.main.render_resume_pdf", return_value="cohere_v2.pdf")
@patch("web.main.tailor_cv", return_value=SAMPLE_TAILORED_CV)
@patch("agents.wellbeing._client")
def test_resume_revise_returns_200_with_filename(mock_wc, mock_tailor, mock_pdf, mock_summarise, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    db, resumes_dir, main_module = setup
    os.makedirs(resumes_dir, exist_ok=True)
    parent_id = record_resume(db, "cohere_v1.pdf", "Cohere", "ML Engineer", job_description="We are hiring ML Engineers.")
    client = TestClient(main_module.app)
    response = client.post("/resume/revise", data={
        "parent_resume_id": parent_id,
        "feedback": "Make the summary shorter.",
    })
    assert response.status_code == 200
    assert "cohere_v2.pdf" in response.text


@patch("web.main.summarise_feedback", return_value="Shorter summary.")
@patch("web.main.render_resume_pdf", return_value="cohere_v2.pdf")
@patch("web.main.tailor_cv", return_value=SAMPLE_TAILORED_CV)
@patch("agents.wellbeing._client")
def test_resume_revise_creates_record_with_correct_parent_id(mock_wc, mock_tailor, mock_pdf, mock_summarise, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    db, resumes_dir, main_module = setup
    os.makedirs(resumes_dir, exist_ok=True)
    parent_id = record_resume(db, "cohere_v1.pdf", "Cohere", "ML Engineer", job_description="JD text.")
    client = TestClient(main_module.app)
    client.post("/resume/revise", data={"parent_resume_id": parent_id, "feedback": "Shorter."})
    resumes = [r for r in __import__("core.resume_store", fromlist=["list_resumes"]).list_resumes(db) if r.parent_id == parent_id]
    assert len(resumes) == 1
    assert resumes[0].parent_id == parent_id


@patch("agents.wellbeing._client")
def test_resume_revise_404_for_missing_parent(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    client = make_client(setup)
    response = client.post("/resume/revise", data={"parent_resume_id": 9999, "feedback": "Shorter."})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# /resume/revise/{id}
# ---------------------------------------------------------------------------

@patch("agents.wellbeing._client")
def test_resume_revise_page_returns_200_with_company_and_jd(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    db, _, main_module = setup
    rid = record_resume(db, "cohere.pdf", "Cohere", "ML Engineer", job_description="We are hiring ML Engineers.")
    client = TestClient(main_module.app)
    response = client.get(f"/resume/revise/{rid}")
    assert response.status_code == 200
    assert "Cohere" in response.text
    assert "We are hiring ML Engineers." in response.text


@patch("agents.wellbeing._client")
def test_resume_revise_page_404_for_no_jd(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    db, _, main_module = setup
    rid = record_resume(db, "cohere.pdf", "Cohere", "ML Engineer")  # no JD
    client = TestClient(main_module.app)
    response = client.get(f"/resume/revise/{rid}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# /resume/revise-from-history
# ---------------------------------------------------------------------------

@patch("web.main.summarise_feedback", return_value="Shorter summary.")
@patch("web.main.render_resume_pdf", return_value="cohere_v2.pdf")
@patch("web.main.tailor_cv", return_value=SAMPLE_TAILORED_CV)
@patch("agents.wellbeing._client")
def test_resume_revise_from_history_redirects_to_history(mock_wc, mock_tailor, mock_pdf, mock_summarise, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    db, resumes_dir, main_module = setup
    os.makedirs(resumes_dir, exist_ok=True)
    parent_id = record_resume(db, "cohere_v1.pdf", "Cohere", "ML Engineer", job_description="JD text.")
    client = TestClient(main_module.app)
    response = client.post("/resume/revise-from-history", data={
        "parent_resume_id": parent_id,
        "job_description": "Updated JD text.",
        "feedback": "Shorter summary.",
    }, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/resume/")
    assert response.headers["location"].endswith("/edit")


# ---------------------------------------------------------------------------
# /resume/{id}/edit
# ---------------------------------------------------------------------------

SAMPLE_TAILORED_JSON = json.dumps({
    "personal": {"name": "Jane Doe", "email": "jane@example.com", "location": "London", "linkedin": "", "github": "", "summary": "ML engineer with 5 years experience."},
    "experience": [{"company": "Acme", "role": "ML Engineer", "start": "2023-01", "end": "present", "bullets": ["Built pipelines."]}],
    "projects": [],
    "education": [{"institution": "Uni", "degree": "BSc", "year": "2021"}],
    "skills": {"languages": ["Python"], "frameworks": [], "tools": [], "other": []},
    "target_role": "ML Engineer",
    "target_company": "Cohere",
})


@patch("agents.wellbeing._client")
def test_resume_edit_page_returns_200_with_summary(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    db, _, main_module = setup
    rid = record_resume(db, "cohere.pdf", "Cohere", "ML Engineer", tailored_json=SAMPLE_TAILORED_JSON)
    client = TestClient(main_module.app)
    response = client.get(f"/resume/{rid}/edit")
    assert response.status_code == 200
    assert "ML engineer with 5 years experience." in response.text


@patch("agents.wellbeing._client")
def test_resume_edit_page_shows_fallback_for_no_json(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    db, _, main_module = setup
    rid = record_resume(db, "cohere.pdf", "Cohere", "ML Engineer")  # no tailored_json
    client = TestClient(main_module.app)
    response = client.get(f"/resume/{rid}/edit")
    assert response.status_code == 200
    assert "Live editing is not available" in response.text


@patch("agents.wellbeing._client")
def test_resume_edit_page_404_for_missing(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    client = make_client(setup)
    response = client.get("/resume/9999/edit")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# /resume/{id}/save
# ---------------------------------------------------------------------------

SAMPLE_EDIT_FORM = {
    "name": "Jane Doe",
    "email": "jane@example.com",
    "location": "London",
    "linkedin": "",
    "github": "",
    "summary": "Updated summary.",
    "exp_0_company": "Acme",
    "exp_0_role": "ML Engineer",
    "exp_0_start": "2023-01",
    "exp_0_end": "present",
    "exp_0_bullet_0": "Built pipelines.",
    "exp_0_bullet_1": "",  # empty bullet — should be dropped
    "languages": "Python, Go",
    "frameworks": "",
    "tools": "",
    "other": "",
    "education_json": '[{"institution": "Uni", "degree": "BSc", "year": "2021"}]',
    "target_role": "ML Engineer",
    "target_company": "Cohere",
}


@patch("web.main.render_resume_pdf", return_value="cohere_edited.pdf")
@patch("agents.wellbeing._client")
def test_resume_edit_save_redirects_to_edit_page(mock_wc, mock_pdf, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    db, resumes_dir, main_module = setup
    os.makedirs(resumes_dir, exist_ok=True)
    rid = record_resume(db, "cohere.pdf", "Cohere", "ML Engineer", tailored_json=SAMPLE_TAILORED_JSON)
    client = TestClient(main_module.app)
    response = client.post(f"/resume/{rid}/save", data=SAMPLE_EDIT_FORM, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/resume/{rid}/edit"


@patch("web.main.render_resume_pdf", return_value="cohere_edited.pdf")
@patch("agents.wellbeing._client")
def test_resume_edit_save_updates_db(mock_wc, mock_pdf, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    db, resumes_dir, main_module = setup
    os.makedirs(resumes_dir, exist_ok=True)
    rid = record_resume(db, "cohere.pdf", "Cohere", "ML Engineer", tailored_json=SAMPLE_TAILORED_JSON)
    client = TestClient(main_module.app)
    client.post(f"/resume/{rid}/save", data=SAMPLE_EDIT_FORM, follow_redirects=False)
    updated = get_resume(db, rid)
    assert updated.filename == "cohere_edited.pdf"
    assert "Updated summary." in updated.tailored_json


@patch("web.main.render_resume_pdf", return_value="cohere_edited.pdf")
@patch("agents.wellbeing._client")
def test_resume_edit_save_drops_empty_bullets(mock_wc, mock_pdf, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    db, resumes_dir, main_module = setup
    os.makedirs(resumes_dir, exist_ok=True)
    rid = record_resume(db, "cohere.pdf", "Cohere", "ML Engineer", tailored_json=SAMPLE_TAILORED_JSON)
    client = TestClient(main_module.app)
    client.post(f"/resume/{rid}/save", data=SAMPLE_EDIT_FORM, follow_redirects=False)
    updated = get_resume(db, rid)
    saved = json.loads(updated.tailored_json)
    bullets = saved["experience"][0]["bullets"]
    assert "" not in bullets
    assert all(b.strip() for b in bullets)


@patch("agents.wellbeing._client")
def test_resume_edit_save_404_for_missing(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_claude_wellbeing()
    client = make_client(setup)
    response = client.post("/resume/9999/save", data=SAMPLE_EDIT_FORM)
    assert response.status_code == 404
