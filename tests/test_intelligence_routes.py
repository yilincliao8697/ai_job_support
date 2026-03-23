import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from core.tracker import init_db
from core.watchlist import add_company
from agents.market_intelligence import SimilarCompany, CompanyPulse


@pytest.fixture(autouse=True)
def setup(monkeypatch, tmp_path):
    db = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db)
    import importlib
    import web.main as main_module
    importlib.reload(main_module)
    init_db(db)
    monkeypatch.setattr(main_module, "DB_PATH", db)
    return db, main_module


def make_client(setup):
    _, main_module = setup
    return TestClient(main_module.app)


def _mock_wellbeing(text="Keep going."):
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


SAMPLE_COMPANIES = [
    SimilarCompany(name="Mistral AI", reason="Series A, LLM focus"),
    SimilarCompany(name="Together AI", reason="Series B, infra"),
]

SAMPLE_PULSE = CompanyPulse(
    company_name="Cohere",
    recent_funding="Series B, $50M",
    headcount_direction="Growing",
    layoff_news="No layoff news",
    open_roles_count="12 roles",
    hiring_signal="Strong hiring window",
    sources=["https://techcrunch.com"],
)


@patch("agents.wellbeing._client")
def test_intelligence_page_returns_200(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_wellbeing()
    client = make_client(setup)
    response = client.get("/intelligence")
    assert response.status_code == 200


@patch("web.main.expand_companies", return_value=SAMPLE_COMPANIES)
@patch("agents.wellbeing._client")
def test_intelligence_expand_returns_company_names(mock_wc, mock_expand, setup):
    mock_wc.return_value.messages.create.return_value = _mock_wellbeing()
    client = make_client(setup)
    response = client.post("/intelligence/expand", data={"job_description": "ML Engineer at Cohere"})
    assert response.status_code == 200
    assert "Mistral AI" in response.text
    assert "Together AI" in response.text


@patch("agents.wellbeing._client")
def test_watchlist_add_returns_updated_list(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_wellbeing()
    client = make_client(setup)
    response = client.post("/intelligence/watchlist/add", data={"company_name": "Cohere"})
    assert response.status_code == 200
    assert "Cohere" in response.text


@patch("agents.wellbeing._client")
def test_company_pulse_page_returns_200(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_wellbeing()
    db, main_module = setup
    company_id = add_company(db, "Cohere")
    client = TestClient(main_module.app)
    response = client.get(f"/companies/{company_id}")
    assert response.status_code == 200


@patch("agents.wellbeing._client")
def test_company_pulse_page_404_for_missing(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_wellbeing()
    client = make_client(setup)
    response = client.get("/companies/9999")
    assert response.status_code == 404


@patch("web.main.get_company_pulse", return_value=SAMPLE_PULSE)
@patch("agents.wellbeing._client")
def test_company_pulse_refresh_returns_pulse_fields(mock_wc, mock_pulse, setup):
    mock_wc.return_value.messages.create.return_value = _mock_wellbeing()
    db, main_module = setup
    company_id = add_company(db, "Cohere")
    client = TestClient(main_module.app)
    response = client.post(f"/companies/{company_id}/pulse")
    assert response.status_code == 200
    assert "Series B" in response.text
    assert "Strong hiring window" in response.text


@patch("agents.wellbeing._client")
def test_company_delete_returns_200(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_wellbeing()
    db, main_module = setup
    company_id = add_company(db, "Cohere")
    client = TestClient(main_module.app)
    response = client.post(f"/companies/{company_id}/delete")
    assert response.status_code == 200


@patch("agents.wellbeing._client")
def test_watchlist_add_with_sector_stores_sector(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_wellbeing()
    db, main_module = setup
    client = TestClient(main_module.app)
    client.post("/intelligence/watchlist/add", data={"company_name": "Stripe", "sector": "Fintech"})
    from core.watchlist import list_companies
    companies = list_companies(db)
    stripe = next(c for c in companies if c.company_name == "Stripe")
    assert stripe.sector == "Fintech"


@patch("agents.wellbeing._client")
def test_watchlist_add_without_sector_succeeds(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_wellbeing()
    client = make_client(setup)
    response = client.post("/intelligence/watchlist/add", data={"company_name": "Cohere"})
    assert response.status_code == 200
