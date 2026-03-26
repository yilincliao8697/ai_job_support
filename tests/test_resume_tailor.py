import json
import pytest
from unittest.mock import patch, MagicMock
from agents.resume_tailor import tailor_cv, summarise_feedback, TailoredCV

SAMPLE_CV_TEXT = """
=== PERSONAL ===
Name: Jane Doe
Email: jane@example.com

=== EXPERIENCE ===
ML Engineer at Acme Corp (2023-01 – present)
  • Built ML pipeline reducing latency by 30%.

=== SKILLS ===
Languages: Python, SQL
"""

SAMPLE_JD = "We are looking for an ML Engineer at Cohere to build LLM systems."

VALID_RESPONSE = {
    "personal": {"name": "Jane Doe", "email": "jane@example.com", "location": "", "linkedin": "", "github": "", "summary": "ML engineer targeting LLM roles."},
    "experience": [{"company": "Acme Corp", "role": "ML Engineer", "start": "2023-01", "end": "present", "bullets": ["Built LLM pipelines at scale."]}],
    "projects": [{"name": "LLM App", "description": "Demo app.", "bullets": ["Built with Claude API."]}],
    "education": [{"institution": "University", "degree": "BSc CS", "year": "2021"}],
    "skills": {"languages": ["Python"], "frameworks": ["PyTorch"], "tools": ["Docker"], "other": []},
    "target_role": "ML Engineer",
    "target_company": "Cohere",
}


def _mock_response(data: dict):
    block = MagicMock()
    block.text = json.dumps(data)
    resp = MagicMock()
    resp.content = [block]
    return resp


@patch("agents.resume_tailor._client")
def test_tailor_cv_returns_tailored_cv_instance(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response(VALID_RESPONSE)
    result = tailor_cv(SAMPLE_CV_TEXT, SAMPLE_JD)
    assert isinstance(result, TailoredCV)


@patch("agents.resume_tailor._client")
def test_tailor_cv_has_nonempty_experience(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response(VALID_RESPONSE)
    result = tailor_cv(SAMPLE_CV_TEXT, SAMPLE_JD)
    assert len(result.experience) > 0


@patch("agents.resume_tailor._client")
def test_tailor_cv_has_personal_info(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response(VALID_RESPONSE)
    result = tailor_cv(SAMPLE_CV_TEXT, SAMPLE_JD)
    assert result.personal.get("name") == "Jane Doe"


@patch("agents.resume_tailor._client")
def test_tailor_cv_sets_target_role_and_company(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response(VALID_RESPONSE)
    result = tailor_cv(SAMPLE_CV_TEXT, SAMPLE_JD)
    assert result.target_role == "ML Engineer"
    assert result.target_company == "Cohere"


@patch("agents.resume_tailor._client")
def test_tailor_cv_raises_on_invalid_json(mock_client):
    block = MagicMock()
    block.text = "This is not JSON at all."
    resp = MagicMock()
    resp.content = [block]
    mock_client.return_value.messages.create.return_value = resp
    with pytest.raises(ValueError, match="invalid JSON"):
        tailor_cv(SAMPLE_CV_TEXT, SAMPLE_JD)


@patch("agents.resume_tailor._client")
def test_tailor_cv_raises_on_missing_fields(mock_client):
    incomplete = {"personal": {"name": "Jane"}, "experience": []}
    mock_client.return_value.messages.create.return_value = _mock_response(incomplete)
    with pytest.raises(ValueError, match="missing required fields"):
        tailor_cv(SAMPLE_CV_TEXT, SAMPLE_JD)


@patch("agents.resume_tailor._client")
def test_tailor_cv_with_revision_context_includes_revision_block(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response(VALID_RESPONSE)
    tailor_cv(SAMPLE_CV_TEXT, SAMPLE_JD, revision_context="Round 1: Emphasise LLM experience.")
    call_args = mock_client.return_value.messages.create.call_args
    prompt = call_args.kwargs["messages"][0]["content"]
    assert "REVISION INSTRUCTIONS" in prompt
    assert "Round 1: Emphasise LLM experience." in prompt


@patch("agents.resume_tailor._client")
def test_tailor_cv_without_revision_context_excludes_revision_block(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response(VALID_RESPONSE)
    tailor_cv(SAMPLE_CV_TEXT, SAMPLE_JD)
    call_args = mock_client.return_value.messages.create.call_args
    prompt = call_args.kwargs["messages"][0]["content"]
    assert "REVISION INSTRUCTIONS" not in prompt


def test_tailored_cv_awards_defaults_to_empty_list():
    cv = TailoredCV(
        personal={}, experience=[], projects=[], education=[],
        skills={}, target_role="", target_company="",
    )
    assert cv.awards == []


def test_tailored_cv_stores_awards_when_passed():
    awards = [{"title": "Best Project", "issuer": "UC Berkeley", "date": "2025-08", "description": "Top capstone."}]
    cv = TailoredCV(
        personal={}, experience=[], projects=[], education=[],
        skills={}, target_role="", target_company="", awards=awards,
    )
    assert cv.awards == awards


@patch("agents.resume_tailor._client")
def test_tailor_cv_populates_awards_from_response(mock_client):
    response_with_awards = {**VALID_RESPONSE, "awards": [{"title": "Hackathon Winner", "issuer": "Y-Combinator", "date": "2025-11", "description": "First place."}]}
    mock_client.return_value.messages.create.return_value = _mock_response(response_with_awards)
    result = tailor_cv(SAMPLE_CV_TEXT, SAMPLE_JD)
    assert len(result.awards) == 1
    assert result.awards[0]["title"] == "Hackathon Winner"


@patch("agents.resume_tailor._client")
def test_tailor_cv_awards_empty_when_omitted_from_response(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response(VALID_RESPONSE)
    result = tailor_cv(SAMPLE_CV_TEXT, SAMPLE_JD)
    assert result.awards == []


@patch("agents.resume_tailor._client")
def test_summarise_feedback_returns_nonempty_string(mock_client):
    block = MagicMock()
    block.text = "Emphasise LLM infrastructure experience; remove 2019 internship."
    resp = MagicMock()
    resp.content = [block]
    mock_client.return_value.messages.create.return_value = resp
    result = summarise_feedback("Please emphasise my LLM infrastructure experience more and remove the 2019 internship entry.")
    assert isinstance(result, str)
    assert len(result) > 0
