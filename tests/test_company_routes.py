import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from core.tracker import init_db
from core.watchlist import add_company


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


@patch("agents.wellbeing._client")
def test_companies_index_returns_200(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_wellbeing()
    client = make_client(setup)
    response = client.get("/companies")
    assert response.status_code == 200


@patch("agents.wellbeing._client")
def test_companies_index_renders_sector_headings(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_wellbeing()
    db, main_module = setup
    add_company(db, "Stripe", sector="Fintech")
    add_company(db, "Cohere", sector="LLM Tooling")
    client = TestClient(main_module.app)
    response = client.get("/companies")
    assert response.status_code == 200
    assert "Fintech" in response.text
    assert "LLM Tooling" in response.text
    assert "Stripe" in response.text
    assert "Cohere" in response.text


@patch("agents.wellbeing._client")
def test_company_edit_form_returns_200_with_sector_input(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_wellbeing()
    db, main_module = setup
    company_id = add_company(db, "Stripe", sector="Fintech")
    client = TestClient(main_module.app)
    response = client.get(f"/companies/{company_id}/edit-form")
    assert response.status_code == 200
    assert 'name="sector"' in response.text


@patch("agents.wellbeing._client")
def test_company_update_details_saves_and_returns_card(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_wellbeing()
    db, main_module = setup
    company_id = add_company(db, "Stripe")
    client = TestClient(main_module.app)
    response = client.post(
        f"/companies/{company_id}/details",
        data={
            "sector": "Fintech",
            "website_url": "https://stripe.com",
            "careers_url": "https://stripe.com/jobs",
        },
    )
    assert response.status_code == 200
    assert "Stripe" in response.text
    assert "Fintech" in response.text
    # Verify persisted
    from core.watchlist import list_companies
    company = next(c for c in list_companies(db) if c.id == company_id)
    assert company.sector == "Fintech"
    assert company.website_url == "https://stripe.com"


@patch("agents.wellbeing._client")
def test_company_card_returns_200_with_company_name(mock_wc, setup):
    mock_wc.return_value.messages.create.return_value = _mock_wellbeing()
    db, main_module = setup
    company_id = add_company(db, "Cohere")
    client = TestClient(main_module.app)
    response = client.get(f"/companies/{company_id}/card")
    assert response.status_code == 200
    assert "Cohere" in response.text
