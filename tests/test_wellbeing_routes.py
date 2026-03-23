import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from core.tracker import init_db, add_application, ApplicationIn


def _mock_response(text: str):
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


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
def test_encouragement_page_returns_200(mock_client, temp_db):
    mock_client.return_value.messages.create.return_value = _mock_response("You've got this.")
    _, main_module = temp_db
    client = make_client(main_module)
    response = client.get("/encouragement")
    assert response.status_code == 200


@patch("agents.wellbeing._client")
def test_encouragement_post_returns_text(mock_client, temp_db):
    mock_client.return_value.messages.create.return_value = _mock_response("That sounds hard. Keep going.")
    _, main_module = temp_db
    client = make_client(main_module)
    response = client.post("/encouragement", data={"user_message": "I'm struggling today"})
    assert response.status_code == 200
    assert "That sounds hard" in response.text


@patch("agents.wellbeing._client")
def test_new_application_shows_encouragement(mock_client, temp_db):
    mock_client.return_value.messages.create.return_value = _mock_response(
        "Great application to Cohere!"
    )
    _, main_module = temp_db
    client = make_client(main_module)
    response = client.post(
        "/applications/new",
        data={
            "company": "Cohere",
            "role_title": "ML Engineer",
            "date_applied": "2026-03-01",
            "status": "applied",
        },
    )
    assert response.status_code == 200
    assert "Great application to Cohere!" in response.text


@patch("agents.wellbeing._client")
def test_status_update_rejected_shows_reframe(mock_client, temp_db):
    mock_client.return_value.messages.create.return_value = _mock_response(
        "Rejection is part of the process."
    )
    db, main_module = temp_db
    app_id = add_application(db, ApplicationIn(
        company="Acme", role_title="Engineer",
        date_applied="2026-01-01", status="applied",
    ))
    client = make_client(main_module)
    response = client.post(
        f"/applications/{app_id}/status",
        data={"status": "rejected"},
    )
    assert response.status_code == 200
    assert "Rejection is part of the process." in response.text
