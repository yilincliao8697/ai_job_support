import json
import pytest
from unittest.mock import patch, MagicMock
from agents.resume_tailor import tailor_cv, TailoredCV

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
