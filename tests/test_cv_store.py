import tempfile
import os
import pytest
import yaml
from core.cv_store import load_cv, get_cv_as_text


@pytest.fixture
def sample_cv_path(tmp_path):
    cv = {
        "personal": {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "location": "London, UK",
            "linkedin": "https://linkedin.com/in/janedoe",
            "github": "https://github.com/janedoe",
            "summary": "ML engineer with 3 years experience.",
        },
        "experience": [
            {
                "company": "Acme Corp",
                "role": "ML Engineer",
                "start": "2023-01",
                "end": "present",
                "tags": ["ml", "python"],
                "bullets": ["Built ML pipeline.", "Reduced latency by 30%."],
            }
        ],
        "projects": [
            {
                "name": "LLM App",
                "description": "A demo LLM app.",
                "tags": ["llm"],
                "bullets": ["Built with FastAPI and Claude."],
            }
        ],
        "education": [
            {"institution": "University", "degree": "BSc CS", "year": "2021"}
        ],
        "skills": {
            "languages": ["Python"],
            "frameworks": ["PyTorch"],
            "tools": ["Docker"],
            "other": [],
        },
    }
    path = tmp_path / "cv.yaml"
    with open(path, "w") as f:
        yaml.dump(cv, f)
    return str(path)


def test_load_cv_returns_dict_with_expected_keys(sample_cv_path):
    cv = load_cv(sample_cv_path)
    assert isinstance(cv, dict)
    for key in ("personal", "experience", "projects", "education", "skills"):
        assert key in cv


def test_load_cv_raises_on_missing_file():
    with pytest.raises(FileNotFoundError):
        load_cv("/nonexistent/path/cv.yaml")


def test_get_cv_as_text_returns_nonempty_string(sample_cv_path):
    text = get_cv_as_text(sample_cv_path)
    assert isinstance(text, str)
    assert len(text) > 0


def test_get_cv_as_text_contains_name(sample_cv_path):
    text = get_cv_as_text(sample_cv_path)
    assert "Jane Doe" in text


def test_get_cv_as_text_contains_experience(sample_cv_path):
    text = get_cv_as_text(sample_cv_path)
    assert "Acme Corp" in text
    assert "ML Engineer" in text


def test_get_cv_as_text_raises_on_missing_file():
    with pytest.raises(FileNotFoundError):
        get_cv_as_text("/nonexistent/path/cv.yaml")
