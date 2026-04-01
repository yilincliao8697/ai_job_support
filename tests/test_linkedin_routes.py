import importlib
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


SAMPLE_POSTS = [
    "First post about LLMs in energy sector.",
    "Second post, different angle on the topic.",
    "Third post, more reflective take.",
]

CV_CONTEXT = "Applied AI engineer. Skills: Python, LLMs."


@pytest.fixture
def client(monkeypatch, tmp_path):
    db = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db)
    import web.main as main_module
    importlib.reload(main_module)
    from core.tracker import init_db
    init_db(db)
    monkeypatch.setattr(main_module, "DB_PATH", db)
    return TestClient(main_module.app), main_module


# ---------------------------------------------------------------------------
# GET /linkedin
# ---------------------------------------------------------------------------

def test_linkedin_page_returns_200(client):
    tc, _ = client
    response = tc.get("/linkedin")
    assert response.status_code == 200


def test_linkedin_page_contains_form(client):
    tc, _ = client
    response = tc.get("/linkedin")
    assert "linkedin-form" in response.text


def test_linkedin_page_contains_category_tiles(client):
    tc, _ = client
    response = tc.get("/linkedin")
    assert "Tech / Tool Experience" in response.text
    assert "Industry Application" in response.text
    assert "Paper or Blog Reaction" in response.text


def test_linkedin_page_contains_tone_selector(client):
    tc, _ = client
    response = tc.get("/linkedin")
    assert "Insightful" in response.text
    assert "Hot Take" in response.text


def test_linkedin_page_contains_url_field(client):
    tc, _ = client
    response = tc.get("/linkedin")
    assert 'name="url"' in response.text


# ---------------------------------------------------------------------------
# POST /linkedin/generate
# ---------------------------------------------------------------------------

@patch("web.main.get_linkedin_context", return_value=CV_CONTEXT)
@patch("web.main.fetch_url_content", return_value="")
@patch("web.main.generate_linkedin_posts", return_value=SAMPLE_POSTS)
def test_generate_returns_200(mock_gen, mock_fetch, mock_ctx, client):
    tc, _ = client
    response = tc.post("/linkedin/generate", data={
        "category": "tech_tool", "topic": "Claude Code", "url": "", "tone": "insightful",
    })
    assert response.status_code == 200


@patch("web.main.get_linkedin_context", return_value=CV_CONTEXT)
@patch("web.main.fetch_url_content", return_value="")
@patch("web.main.generate_linkedin_posts", return_value=SAMPLE_POSTS)
def test_generate_returns_all_three_posts(mock_gen, mock_fetch, mock_ctx, client):
    tc, _ = client
    response = tc.post("/linkedin/generate", data={
        "category": "tech_tool", "topic": "Claude Code", "url": "", "tone": "insightful",
    })
    assert "First post about LLMs" in response.text
    assert "Second post" in response.text
    assert "Third post" in response.text


@patch("web.main.get_linkedin_context", return_value=CV_CONTEXT)
@patch("web.main.fetch_url_content", return_value="")
@patch("web.main.generate_linkedin_posts", return_value=SAMPLE_POSTS)
def test_generate_passes_category_and_tone_to_agent(mock_gen, mock_fetch, mock_ctx, client):
    tc, _ = client
    tc.post("/linkedin/generate", data={
        "category": "industry_application", "topic": "AI in utilities", "url": "", "tone": "hot_take",
    })
    mock_gen.assert_called_once()
    args = mock_gen.call_args
    assert args.args[1] == "industry_application"
    assert args.args[3] == "hot_take"


@patch("web.main.get_linkedin_context", return_value=CV_CONTEXT)
@patch("web.main.fetch_url_content", return_value="Article content here.")
@patch("web.main.generate_linkedin_posts", return_value=SAMPLE_POSTS)
def test_generate_calls_fetch_url_when_url_provided(mock_gen, mock_fetch, mock_ctx, client):
    tc, _ = client
    tc.post("/linkedin/generate", data={
        "category": "paper_blog", "topic": "attention paper",
        "url": "https://example.com/paper", "tone": "insightful",
    })
    mock_fetch.assert_called_once_with("https://example.com/paper")


@patch("web.main.get_linkedin_context", return_value=CV_CONTEXT)
@patch("web.main.fetch_url_content", return_value="")
@patch("web.main.generate_linkedin_posts", return_value=SAMPLE_POSTS)
def test_generate_skips_fetch_when_url_empty(mock_gen, mock_fetch, mock_ctx, client):
    tc, _ = client
    tc.post("/linkedin/generate", data={
        "category": "tech_tool", "topic": "Claude Code", "url": "", "tone": "insightful",
    })
    mock_fetch.assert_not_called()


@patch("web.main.get_linkedin_context", return_value=CV_CONTEXT)
@patch("web.main.fetch_url_content", return_value="")
@patch("web.main.generate_linkedin_posts", return_value=SAMPLE_POSTS)
def test_generate_response_contains_show_me_another_buttons(mock_gen, mock_fetch, mock_ctx, client):
    tc, _ = client
    response = tc.post("/linkedin/generate", data={
        "category": "tech_tool", "topic": "Claude Code", "url": "", "tone": "insightful",
    })
    assert "Show me another" in response.text


@patch("web.main.get_linkedin_context", return_value=CV_CONTEXT)
@patch("web.main.fetch_url_content", return_value="")
@patch("web.main.generate_linkedin_posts", return_value=SAMPLE_POSTS)
def test_generate_response_contains_copy_buttons(mock_gen, mock_fetch, mock_ctx, client):
    tc, _ = client
    response = tc.post("/linkedin/generate", data={
        "category": "tech_tool", "topic": "Claude Code", "url": "", "tone": "insightful",
    })
    assert "Copy" in response.text


# ---------------------------------------------------------------------------
# POST /linkedin/regenerate
# ---------------------------------------------------------------------------

@patch("web.main.get_linkedin_context", return_value=CV_CONTEXT)
@patch("web.main.fetch_url_content", return_value="")
@patch("web.main.regenerate_linkedin_post", return_value="A fresh new take on the topic.")
def test_regenerate_returns_200(mock_regen, mock_fetch, mock_ctx, client):
    tc, _ = client
    response = tc.post("/linkedin/regenerate", data={
        "category": "tech_tool", "topic": "Claude Code",
        "url": "", "tone": "insightful", "slot": "1",
    })
    assert response.status_code == 200


@patch("web.main.get_linkedin_context", return_value=CV_CONTEXT)
@patch("web.main.fetch_url_content", return_value="")
@patch("web.main.regenerate_linkedin_post", return_value="A fresh new take on the topic.")
def test_regenerate_returns_new_post_text(mock_regen, mock_fetch, mock_ctx, client):
    tc, _ = client
    response = tc.post("/linkedin/regenerate", data={
        "category": "tech_tool", "topic": "Claude Code",
        "url": "", "tone": "insightful", "slot": "0",
    })
    assert "A fresh new take on the topic." in response.text


@patch("web.main.get_linkedin_context", return_value=CV_CONTEXT)
@patch("web.main.fetch_url_content", return_value="")
@patch("web.main.regenerate_linkedin_post", return_value="A fresh new take on the topic.")
def test_regenerate_targets_correct_slot(mock_regen, mock_fetch, mock_ctx, client):
    tc, _ = client
    response = tc.post("/linkedin/regenerate", data={
        "category": "tech_tool", "topic": "Claude Code",
        "url": "", "tone": "insightful", "slot": "2",
    })
    assert 'id="post-slot-2"' in response.text


@patch("web.main.get_linkedin_context", return_value=CV_CONTEXT)
@patch("web.main.fetch_url_content", return_value="Article content.")
@patch("web.main.regenerate_linkedin_post", return_value="Post with URL context.")
def test_regenerate_fetches_url_when_provided(mock_regen, mock_fetch, mock_ctx, client):
    tc, _ = client
    tc.post("/linkedin/regenerate", data={
        "category": "paper_blog", "topic": "some paper",
        "url": "https://example.com/paper", "tone": "insightful", "slot": "0",
    })
    mock_fetch.assert_called_once_with("https://example.com/paper")
