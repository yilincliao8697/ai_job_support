import importlib
import pytest
import yaml
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from agents.cv_from_pdf import extract_pdf_text, cv_yaml_from_pdf


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_claude_response(text: str):
    block = MagicMock()
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


SAMPLE_YAML = """personal:
  name: Jane Doe
  email: jane@example.com
  summary: ML engineer.
experience:
  - company: Acme Corp
    role: ML Engineer
    start: "2023-01"
    end: present
    bullets:
      - Built LLM pipelines.
skills:
  languages:
    - Python
"""

EXAMPLE_SCHEMA = """personal:
  name: "Your Name"
  email: "you@email.com"
experience:
  - company: "Company Name"
    role: "Job Title"
"""


# ---------------------------------------------------------------------------
# extract_pdf_text
# ---------------------------------------------------------------------------

def test_extract_pdf_text_returns_string():
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Jane Doe\nML Engineer"
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    with patch("agents.cv_from_pdf.pypdf.PdfReader", return_value=mock_reader):
        result = extract_pdf_text(b"fake pdf bytes")

    assert isinstance(result, str)
    assert "Jane Doe" in result


def test_extract_pdf_text_joins_multiple_pages():
    pages = [MagicMock(), MagicMock()]
    pages[0].extract_text.return_value = "Page one content."
    pages[1].extract_text.return_value = "Page two content."
    mock_reader = MagicMock()
    mock_reader.pages = pages

    with patch("agents.cv_from_pdf.pypdf.PdfReader", return_value=mock_reader):
        result = extract_pdf_text(b"fake pdf bytes")

    assert "Page one content." in result
    assert "Page two content." in result


def test_extract_pdf_text_handles_none_page_text():
    mock_page = MagicMock()
    mock_page.extract_text.return_value = None
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    with patch("agents.cv_from_pdf.pypdf.PdfReader", return_value=mock_reader):
        result = extract_pdf_text(b"fake pdf bytes")

    assert result == ""


def test_extract_pdf_text_strips_whitespace():
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "  Jane Doe  "
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    with patch("agents.cv_from_pdf.pypdf.PdfReader", return_value=mock_reader):
        result = extract_pdf_text(b"fake pdf bytes")

    assert result == result.strip()


# ---------------------------------------------------------------------------
# cv_yaml_from_pdf
# ---------------------------------------------------------------------------

@patch("agents.cv_from_pdf.anthropic.Anthropic")
def test_cv_yaml_from_pdf_returns_string(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response(SAMPLE_YAML)
    result = cv_yaml_from_pdf("Jane Doe, ML Engineer", EXAMPLE_SCHEMA)
    assert isinstance(result, str)


@patch("agents.cv_from_pdf.anthropic.Anthropic")
def test_cv_yaml_from_pdf_output_is_valid_yaml(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response(SAMPLE_YAML)
    result = cv_yaml_from_pdf("Jane Doe, ML Engineer", EXAMPLE_SCHEMA)
    parsed = yaml.safe_load(result)
    assert isinstance(parsed, dict)


@patch("agents.cv_from_pdf.anthropic.Anthropic")
def test_cv_yaml_from_pdf_includes_pdf_text_in_prompt(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response(SAMPLE_YAML)
    cv_yaml_from_pdf("Unique CV content here", EXAMPLE_SCHEMA)
    call_args = mock_anthropic.return_value.messages.create.call_args
    prompt = call_args.kwargs["messages"][0]["content"]
    assert "Unique CV content here" in prompt


@patch("agents.cv_from_pdf.anthropic.Anthropic")
def test_cv_yaml_from_pdf_includes_schema_in_prompt(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response(SAMPLE_YAML)
    cv_yaml_from_pdf("Some CV text", "unique_schema_marker: true")
    call_args = mock_anthropic.return_value.messages.create.call_args
    prompt = call_args.kwargs["messages"][0]["content"]
    assert "unique_schema_marker" in prompt


@patch("agents.cv_from_pdf.anthropic.Anthropic")
def test_cv_yaml_from_pdf_strips_response_whitespace(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response(
        "  \n" + SAMPLE_YAML + "\n  "
    )
    result = cv_yaml_from_pdf("Some CV text", EXAMPLE_SCHEMA)
    assert result == result.strip()


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch, tmp_path):
    cv_path = str(tmp_path / "cv.yaml")
    with open(cv_path, "w") as f:
        f.write("")
    monkeypatch.setenv("CV_PATH", cv_path)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    import web.main as main_module
    importlib.reload(main_module)
    from core.tracker import init_db
    init_db(str(tmp_path / "test.db"))
    return TestClient(main_module.app), main_module, cv_path


def test_upload_pdf_no_file_redirects(client):
    tc, _, _ = client
    response = tc.post("/cv/upload-pdf", files={"pdf": ("", b"", "application/pdf")},
                       follow_redirects=False)
    assert response.status_code == 303


@patch("web.main.extract_pdf_text", return_value="")
def test_upload_pdf_empty_text_shows_error(mock_extract, client):
    tc, _, _ = client
    response = tc.post("/cv/upload-pdf",
                       files={"pdf": ("cv.pdf", b"fake pdf", "application/pdf")})
    assert response.status_code == 200
    assert "Could not extract text" in response.text


@patch("web.main.extract_pdf_text", return_value="Jane Doe CV content")
@patch("web.main.cv_yaml_from_pdf", return_value=SAMPLE_YAML)
def test_upload_pdf_valid_writes_file_and_redirects(mock_yaml, mock_extract, client):
    tc, _, cv_path = client
    response = tc.post("/cv/upload-pdf",
                       files={"pdf": ("cv.pdf", b"fake pdf", "application/pdf")},
                       follow_redirects=False)
    assert response.status_code == 303
    with open(cv_path) as f:
        written = f.read()
    assert "Jane Doe" in written


@patch("web.main.extract_pdf_text", return_value="Jane Doe CV content")
@patch("web.main.cv_yaml_from_pdf", return_value="invalid: yaml: !!!")
def test_upload_pdf_invalid_yaml_shows_error(mock_yaml, mock_extract, client):
    tc, _, _ = client
    response = tc.post("/cv/upload-pdf",
                       files={"pdf": ("cv.pdf", b"fake pdf", "application/pdf")})
    assert response.status_code == 200
    assert "invalid YAML" in response.text


def test_cv_edit_page_passes_cv_exists_false_when_empty(client):
    tc, _, _ = client
    response = tc.get("/cv/edit")
    assert response.status_code == 200
    assert "overwrite" not in response.text


def test_cv_edit_page_passes_cv_exists_true_when_content_present(client):
    tc, main_module, cv_path = client
    with open(cv_path, "w") as f:
        f.write(SAMPLE_YAML)
    main_module.CV_PATH = cv_path
    response = tc.get("/cv/edit")
    assert response.status_code == 200
    assert "overwrite" in response.text
