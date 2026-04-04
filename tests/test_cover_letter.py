import importlib
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from agents.cover_letter import generate_cover_letter, TONES
from core.cover_letter_store import (
    init_cover_letters_table, save_cover_letter, get_cover_letter,
    list_cover_letters, delete_cover_letter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_claude_response(text: str):
    block = MagicMock()
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


SAMPLE_LETTER = """Dear Hiring Team,

Your work on large-scale ML infrastructure caught my attention because it maps directly to what I've been building for the past three years. At Acme Corp I led the migration of our model serving layer to a distributed architecture, cutting p99 latency by 40% — the kind of infrastructure challenge your JD describes.

In the previous role at Beta Ltd I designed the feature pipeline that now processes 50 million events daily, working closely with product and data science to translate ambiguous requirements into reliable systems. I also mentored two junior engineers through their first production deployments.

I'd welcome the chance to talk through how my background fits what you're building. Happy to connect at your convenience."""


# ---------------------------------------------------------------------------
# TONES constant
# ---------------------------------------------------------------------------

def test_tones_has_three_entries():
    assert len(TONES) == 3


def test_tones_has_expected_keys():
    assert set(TONES.keys()) == {"professional", "warm", "enthusiastic"}


# ---------------------------------------------------------------------------
# generate_cover_letter
# ---------------------------------------------------------------------------

@patch("agents.cover_letter.anthropic.Anthropic")
def test_generate_cover_letter_returns_string(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response(SAMPLE_LETTER)
    result = generate_cover_letter(
        job_description="ML engineer role",
        cv_text="Experienced ML engineer.",
        tone="professional",
    )
    assert isinstance(result, str)
    assert len(result) > 0


@patch("agents.cover_letter.anthropic.Anthropic")
def test_generate_cover_letter_strips_whitespace(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response(
        "  \n" + SAMPLE_LETTER + "\n  "
    )
    result = generate_cover_letter("JD text", "CV text")
    assert result == result.strip()


@patch("agents.cover_letter.anthropic.Anthropic")
def test_generate_cover_letter_includes_jd_in_prompt(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response(SAMPLE_LETTER)
    generate_cover_letter("unique_jd_marker_xyz", "CV text")
    call_args = mock_anthropic.return_value.messages.create.call_args
    prompt = call_args.kwargs["messages"][0]["content"]
    assert "unique_jd_marker_xyz" in prompt


@patch("agents.cover_letter.anthropic.Anthropic")
def test_generate_cover_letter_includes_cv_in_prompt(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response(SAMPLE_LETTER)
    generate_cover_letter("JD text", "unique_cv_marker_abc")
    call_args = mock_anthropic.return_value.messages.create.call_args
    prompt = call_args.kwargs["messages"][0]["content"]
    assert "unique_cv_marker_abc" in prompt


@patch("agents.cover_letter.anthropic.Anthropic")
def test_generate_cover_letter_includes_personal_note_in_prompt(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response(SAMPLE_LETTER)
    generate_cover_letter("JD text", "CV text", personal_note="unique_note_marker")
    call_args = mock_anthropic.return_value.messages.create.call_args
    prompt = call_args.kwargs["messages"][0]["content"]
    assert "unique_note_marker" in prompt


@patch("agents.cover_letter.anthropic.Anthropic")
def test_generate_cover_letter_skips_personal_note_if_blank(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response(SAMPLE_LETTER)
    generate_cover_letter("JD text", "CV text", personal_note="   ")
    call_args = mock_anthropic.return_value.messages.create.call_args
    prompt = call_args.kwargs["messages"][0]["content"]
    assert "Additional context" not in prompt


# ---------------------------------------------------------------------------
# cover_letter_store
# ---------------------------------------------------------------------------

@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_cover_letters_table(db_path)
    return db_path


def test_save_and_get_cover_letter(db):
    cl_id = save_cover_letter(db, content="Dear Hiring Team,\n\nLetter body.", tone="professional")
    record = get_cover_letter(db, cl_id)
    assert record is not None
    assert record.content == "Dear Hiring Team,\n\nLetter body."
    assert record.tone == "professional"


def test_save_cover_letter_with_metadata(db):
    cl_id = save_cover_letter(
        db, content="Letter.", tone="warm",
        job_title="ML Engineer", company="Acme Corp"
    )
    record = get_cover_letter(db, cl_id)
    assert record.job_title == "ML Engineer"
    assert record.company == "Acme Corp"


def test_save_cover_letter_with_application_id(db):
    cl_id = save_cover_letter(db, content="Letter.", tone="professional", application_id=42)
    record = get_cover_letter(db, cl_id)
    assert record.application_id == 42


def test_get_cover_letter_returns_none_for_missing(db):
    assert get_cover_letter(db, 9999) is None


def test_list_cover_letters_returns_newest_first(db):
    id1 = save_cover_letter(db, content="First.", tone="professional")
    id2 = save_cover_letter(db, content="Second.", tone="warm")
    letters = list_cover_letters(db)
    assert letters[0].id == id2
    assert letters[1].id == id1


def test_list_cover_letters_empty(db):
    assert list_cover_letters(db) == []


def test_delete_cover_letter(db):
    cl_id = save_cover_letter(db, content="To delete.", tone="professional")
    delete_cover_letter(db, cl_id)
    assert get_cover_letter(db, cl_id) is None


def test_delete_nonexistent_is_safe(db):
    delete_cover_letter(db, 9999)  # should not raise


def test_init_cover_letters_table_is_idempotent(db):
    init_cover_letters_table(db)  # call a second time — should not raise or duplicate


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch, tmp_path):
    cv_path = str(tmp_path / "cv.yaml")
    with open(cv_path, "w") as f:
        f.write("personal:\n  name: Test User\n  summary: ML engineer.\n")
    monkeypatch.setenv("CV_PATH", cv_path)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    import web.main as main_module
    importlib.reload(main_module)
    from core.tracker import init_db
    init_db(str(tmp_path / "test.db"))
    return TestClient(main_module.app), main_module


def test_cover_letter_page_renders(client):
    tc, _ = client
    response = tc.get("/cover-letter")
    assert response.status_code == 200
    assert "Cover Letter" in response.text


def test_cover_letter_page_shows_tone_options(client):
    tc, _ = client
    response = tc.get("/cover-letter")
    assert "professional" in response.text
    assert "warm" in response.text
    assert "enthusiastic" in response.text


@patch("web.main.generate_cover_letter", return_value=SAMPLE_LETTER)
def test_cover_letter_generate_returns_partial(mock_gen, client):
    tc, _ = client
    response = tc.post("/cover-letter/generate", data={
        "job_description": "Senior ML Engineer at Acme",
        "tone": "professional",
        "job_title": "ML Engineer",
        "company": "Acme",
        "personal_note": "",
    })
    assert response.status_code == 200
    assert "Dear Hiring Team" in response.text


@patch("web.main.generate_cover_letter", return_value=SAMPLE_LETTER)
def test_cover_letter_generate_saves_to_db(mock_gen, client):
    tc, main_module = client
    tc.post("/cover-letter/generate", data={
        "job_description": "ML Engineer role",
        "tone": "warm",
        "job_title": "ML Engineer",
        "company": "Beta Ltd",
        "personal_note": "",
    })
    letters = list_cover_letters(main_module.DB_PATH)
    assert len(letters) == 1
    assert letters[0].company == "Beta Ltd"
    assert letters[0].tone == "warm"


def test_cover_letter_history_page_renders(client):
    tc, _ = client
    response = tc.get("/cover-letter/history")
    assert response.status_code == 200


def test_cover_letter_history_shows_empty_state(client):
    tc, _ = client
    response = tc.get("/cover-letter/history")
    assert "No cover letters yet" in response.text


@patch("web.main.generate_cover_letter", return_value=SAMPLE_LETTER)
def test_cover_letter_history_shows_saved_entries(mock_gen, client):
    tc, _ = client
    tc.post("/cover-letter/generate", data={
        "job_description": "Role", "tone": "professional",
        "job_title": "Data Scientist", "company": "Gamma Inc", "personal_note": "",
    })
    response = tc.get("/cover-letter/history")
    assert "Data Scientist" in response.text
    assert "Gamma Inc" in response.text


@patch("web.main.generate_cover_letter", return_value=SAMPLE_LETTER)
def test_cover_letter_delete(mock_gen, client):
    tc, main_module = client
    tc.post("/cover-letter/generate", data={
        "job_description": "Role", "tone": "professional",
        "job_title": "", "company": "", "personal_note": "",
    })
    letters = list_cover_letters(main_module.DB_PATH)
    cl_id = letters[0].id
    response = tc.post(f"/cover-letter/history/{cl_id}/delete")
    assert response.status_code == 200
    assert list_cover_letters(main_module.DB_PATH) == []
