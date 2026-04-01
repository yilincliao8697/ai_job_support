import yaml
import pytest
from unittest.mock import MagicMock, patch
from agents.linkedin_post import (
    CATEGORIES,
    TONES,
    get_linkedin_context,
    fetch_url_content,
    generate_linkedin_posts,
    regenerate_linkedin_post,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_cv_path(tmp_path):
    cv = {
        "personal": {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "location": "London, UK",
            "linkedin": "https://linkedin.com/in/janedoe",
            "github": "https://github.com/janedoe",
            "summary": "Applied AI engineer targeting LLM and energy sector roles.",
        },
        "experience": [
            {
                "company": "Acme Corp",
                "role": "ML Engineer",
                "start": "2023-01",
                "end": "present",
                "tags": ["ml", "python", "llm"],
                "bullets": [
                    "Built an LLM pipeline reducing latency by 30%.",
                    "Deployed RAG system for internal knowledge base.",
                    "Mentored two junior engineers on ML best practices.",
                ],
            },
            {
                "company": "Grid Co",
                "role": "Data Scientist",
                "start": "2021-06",
                "end": "2022-12",
                "tags": ["utilities", "python", "forecasting"],
                "bullets": [
                    "Built demand forecasting models for energy grid.",
                ],
            },
        ],
        "projects": [
            {
                "name": "ClaudeCode Helper",
                "description": "A CLI tool that wraps Claude Code for team workflows.",
                "tags": ["llm", "python", "cli"],
                "bullets": ["Built with Anthropic SDK."],
            }
        ],
        "education": [
            {"institution": "University of Edinburgh", "degree": "BSc Computer Science", "year": "2021"}
        ],
        "skills": {
            "languages": ["Python", "SQL"],
            "frameworks": ["FastAPI", "PyTorch"],
            "tools": ["Docker", "Git"],
            "other": ["LLM fine-tuning", "RAG pipelines"],
        },
    }
    path = tmp_path / "cv.yaml"
    with open(path, "w") as f:
        yaml.dump(cv, f)
    return str(path)


def _mock_claude_response(text: str):
    """Build a mock Anthropic messages.create response."""
    block = MagicMock()
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_categories_has_expected_keys():
    assert set(CATEGORIES.keys()) == {
        "tech_tool", "industry_application", "paper_blog", "tip_howto", "career_reflection"
    }


def test_tones_has_expected_keys():
    assert set(TONES.keys()) == {
        "insightful", "conversational", "hot_take", "practical", "reflective"
    }


# ---------------------------------------------------------------------------
# get_linkedin_context
# ---------------------------------------------------------------------------

def test_get_linkedin_context_returns_nonempty_string(sample_cv_path):
    result = get_linkedin_context(sample_cv_path)
    assert isinstance(result, str)
    assert len(result) > 0


def test_get_linkedin_context_contains_summary(sample_cv_path):
    result = get_linkedin_context(sample_cv_path)
    assert "Applied AI engineer" in result


def test_get_linkedin_context_contains_experience(sample_cv_path):
    result = get_linkedin_context(sample_cv_path)
    assert "Acme Corp" in result
    assert "ML Engineer" in result


def test_get_linkedin_context_contains_skills(sample_cv_path):
    result = get_linkedin_context(sample_cv_path)
    assert "Python" in result


def test_get_linkedin_context_contains_projects(sample_cv_path):
    result = get_linkedin_context(sample_cv_path)
    assert "ClaudeCode Helper" in result


def test_get_linkedin_context_excludes_email(sample_cv_path):
    result = get_linkedin_context(sample_cv_path)
    assert "jane@example.com" not in result


def test_get_linkedin_context_excludes_linkedin_url(sample_cv_path):
    result = get_linkedin_context(sample_cv_path)
    assert "linkedin.com/in/janedoe" not in result


def test_get_linkedin_context_excludes_github_url(sample_cv_path):
    result = get_linkedin_context(sample_cv_path)
    assert "github.com/janedoe" not in result


def test_get_linkedin_context_limits_to_four_roles(tmp_path):
    """Only the first 4 experience entries should appear."""
    cv = {
        "personal": {},
        "experience": [
            {"company": f"Company{i}", "role": "Engineer", "start": "2020", "end": "present",
             "tags": [], "bullets": []}
            for i in range(6)
        ],
        "projects": [],
        "skills": {},
    }
    path = tmp_path / "cv.yaml"
    with open(path, "w") as f:
        yaml.dump(cv, f)
    result = get_linkedin_context(str(path))
    assert "Company4" not in result
    assert "Company5" not in result


# ---------------------------------------------------------------------------
# fetch_url_content
# ---------------------------------------------------------------------------

def test_fetch_url_content_returns_cleaned_text():
    html = "<html><body><h1>Hello World</h1><p>Some content here.</p></body></html>"
    mock_response = MagicMock()
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()

    with patch("agents.linkedin_post.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_response
        result = fetch_url_content("https://example.com/article")

    assert "Hello World" in result
    assert "<h1>" not in result
    assert "<p>" not in result


def test_fetch_url_content_strips_html_tags():
    html = "<div class='foo'><span>Clean text</span></div>"
    mock_response = MagicMock()
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()

    with patch("agents.linkedin_post.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_response
        result = fetch_url_content("https://example.com")

    assert "Clean text" in result
    assert "<" not in result


def test_fetch_url_content_truncates_to_3000_chars():
    html = "<p>" + ("x" * 5000) + "</p>"
    mock_response = MagicMock()
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()

    with patch("agents.linkedin_post.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_response
        result = fetch_url_content("https://example.com")

    assert len(result) <= 3000


def test_fetch_url_content_returns_empty_on_http_error():
    with patch("agents.linkedin_post.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.side_effect = Exception("Connection refused")
        result = fetch_url_content("https://example.com/broken")

    assert result == ""


def test_fetch_url_content_returns_empty_on_bad_status():
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("404")

    with patch("agents.linkedin_post.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_response
        result = fetch_url_content("https://example.com/missing")

    assert result == ""


# ---------------------------------------------------------------------------
# generate_linkedin_posts
# ---------------------------------------------------------------------------

SAMPLE_THREE_POSTS = (
    "Post one about LLMs in energy.\n\nMore detail here."
    "\n---\n"
    "Post two taking a different angle."
    "\n---\n"
    "Post three, more reflective take."
)

SAMPLE_CV_CONTEXT = "Applied AI engineer. Skills: Python, LLMs. Experience: ML Engineer at Acme Corp."


@patch("agents.linkedin_post.anthropic.Anthropic")
def test_generate_linkedin_posts_returns_list(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response(SAMPLE_THREE_POSTS)
    result = generate_linkedin_posts(SAMPLE_CV_CONTEXT, "tech_tool", "Claude Code", "insightful")
    assert isinstance(result, list)


@patch("agents.linkedin_post.anthropic.Anthropic")
def test_generate_linkedin_posts_returns_three_by_default(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response(SAMPLE_THREE_POSTS)
    result = generate_linkedin_posts(SAMPLE_CV_CONTEXT, "tech_tool", "Claude Code", "insightful")
    assert len(result) == 3


@patch("agents.linkedin_post.anthropic.Anthropic")
def test_generate_linkedin_posts_each_item_is_string(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response(SAMPLE_THREE_POSTS)
    result = generate_linkedin_posts(SAMPLE_CV_CONTEXT, "tech_tool", "Claude Code", "insightful")
    assert all(isinstance(p, str) for p in result)


@patch("agents.linkedin_post.anthropic.Anthropic")
def test_generate_linkedin_posts_strips_whitespace(mock_anthropic):
    raw = "  Post one content.  \n---\n  Post two content.  \n---\n  Post three.  "
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response(raw)
    result = generate_linkedin_posts(SAMPLE_CV_CONTEXT, "tech_tool", "Claude Code", "insightful")
    for post in result:
        assert post == post.strip()


@patch("agents.linkedin_post.anthropic.Anthropic")
def test_generate_linkedin_posts_respects_count(mock_anthropic):
    raw = "Single post only."
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response(raw)
    result = generate_linkedin_posts(SAMPLE_CV_CONTEXT, "tech_tool", "Claude Code", "insightful", count=1)
    assert len(result) == 1


@patch("agents.linkedin_post.anthropic.Anthropic")
def test_generate_linkedin_posts_includes_url_content_in_prompt(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response(SAMPLE_THREE_POSTS)
    generate_linkedin_posts(
        SAMPLE_CV_CONTEXT, "paper_blog", "attention mechanism", "insightful",
        url_content="Transformers are based on self-attention.",
    )
    call_args = mock_anthropic.return_value.messages.create.call_args
    prompt = call_args.kwargs["messages"][0]["content"]
    assert "Transformers are based on self-attention." in prompt


@patch("agents.linkedin_post.anthropic.Anthropic")
def test_generate_linkedin_posts_omits_url_section_when_empty(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response(SAMPLE_THREE_POSTS)
    generate_linkedin_posts(SAMPLE_CV_CONTEXT, "tech_tool", "Claude Code", "insightful", url_content="")
    call_args = mock_anthropic.return_value.messages.create.call_args
    prompt = call_args.kwargs["messages"][0]["content"]
    assert "Source material" not in prompt


@patch("agents.linkedin_post.anthropic.Anthropic")
def test_generate_linkedin_posts_includes_category_label_in_prompt(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response(SAMPLE_THREE_POSTS)
    generate_linkedin_posts(SAMPLE_CV_CONTEXT, "industry_application", "utilities AI", "insightful")
    call_args = mock_anthropic.return_value.messages.create.call_args
    prompt = call_args.kwargs["messages"][0]["content"]
    assert "Industry Application" in prompt


@patch("agents.linkedin_post.anthropic.Anthropic")
def test_generate_linkedin_posts_includes_tone_label_in_prompt(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response(SAMPLE_THREE_POSTS)
    generate_linkedin_posts(SAMPLE_CV_CONTEXT, "tech_tool", "Claude Code", "hot_take")
    call_args = mock_anthropic.return_value.messages.create.call_args
    prompt = call_args.kwargs["messages"][0]["content"]
    assert "Hot Take" in prompt


# ---------------------------------------------------------------------------
# regenerate_linkedin_post
# ---------------------------------------------------------------------------

@patch("agents.linkedin_post.anthropic.Anthropic")
def test_regenerate_linkedin_post_returns_string(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response("A fresh take on the topic.")
    result = regenerate_linkedin_post(SAMPLE_CV_CONTEXT, "tech_tool", "Claude Code", "insightful")
    assert isinstance(result, str)
    assert len(result) > 0


@patch("agents.linkedin_post.anthropic.Anthropic")
def test_regenerate_linkedin_post_returns_single_post_not_list(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _mock_claude_response("A fresh take on the topic.")
    result = regenerate_linkedin_post(SAMPLE_CV_CONTEXT, "tech_tool", "Claude Code", "insightful")
    assert not isinstance(result, list)
