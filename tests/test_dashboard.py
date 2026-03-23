import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from core.tracker import init_db, add_application, ApplicationIn


def _mock_claude(text="Keep going."):
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


@pytest.fixture(autouse=True)
def temp_db(monkeypatch, tmp_path):
    db = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db)
    import importlib
    import web.main as main_module
    importlib.reload(main_module)
    init_db(db)
    monkeypatch.setattr(main_module, "DB_PATH", db)
    return db, main_module


def make_client(main_module):
    return TestClient(main_module.app)


@patch("agents.wellbeing._client")
def test_dashboard_returns_200(mock_client, temp_db):
    mock_client.return_value.messages.create.return_value = _mock_claude()
    _, main_module = temp_db
    client = make_client(main_module)
    response = client.get("/")
    assert response.status_code == 200


@patch("agents.wellbeing._client")
def test_dashboard_contains_effort_section(mock_client, temp_db):
    mock_client.return_value.messages.create.return_value = _mock_claude()
    _, main_module = temp_db
    client = make_client(main_module)
    response = client.get("/")
    assert "Your effort so far" in response.text


@patch("agents.wellbeing._client")
def test_dashboard_contains_all_module_cards(mock_client, temp_db):
    mock_client.return_value.messages.create.return_value = _mock_claude()
    _, main_module = temp_db
    client = make_client(main_module)
    response = client.get("/")
    assert "Market Intelligence" in response.text
    assert "Resume Tailor" in response.text
    assert "Applications" in response.text
    assert "Need a boost" in response.text


@patch("agents.wellbeing._client")
def test_dashboard_empty_state_with_no_applications(mock_client, temp_db):
    mock_client.return_value.messages.create.return_value = _mock_claude()
    _, main_module = temp_db
    client = make_client(main_module)
    response = client.get("/")
    assert "No applications yet" in response.text


@patch("agents.wellbeing._client")
def test_dashboard_shows_total_count_with_applications(mock_client, temp_db):
    mock_client.return_value.messages.create.return_value = _mock_claude()
    db, main_module = temp_db
    for i in range(3):
        add_application(db, ApplicationIn(
            company=f"Company {i}", role_title="Engineer",
            date_applied="2026-03-01", status="applied",
        ))
    client = make_client(main_module)
    response = client.get("/")
    assert "3 applications" in response.text
