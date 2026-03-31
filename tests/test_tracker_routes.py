import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from core.tracker import init_db, add_application, get_application, ApplicationIn


def _mock_claude(text="Well done!"):
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


@pytest.fixture(autouse=True)
def temp_db(monkeypatch, tmp_path):
    db = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db)
    # Re-import main so it picks up the patched DB_PATH
    import importlib
    import web.main as main_module
    importlib.reload(main_module)
    init_db(db)
    monkeypatch.setattr(main_module, "DB_PATH", db)
    return db, main_module


def make_client(main_module):
    return TestClient(main_module.app)


def test_applications_list_returns_200(temp_db):
    _, main_module = temp_db
    client = make_client(main_module)
    response = client.get("/applications")
    assert response.status_code == 200


@patch("agents.wellbeing._client")
def test_applications_new_post_redirects(mock_client, temp_db):
    mock_client.return_value.messages.create.return_value = _mock_claude("Great application!")
    _, main_module = temp_db
    client = make_client(main_module)
    response = client.post(
        "/applications/new",
        data={
            "company": "Acme Corp",
            "role_title": "ML Engineer",
            "date_applied": "2026-03-01",
            "status": "applied",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/applications"


@patch("agents.wellbeing._client")
def test_applications_new_post_sets_encouragement_cookie(mock_client, temp_db):
    mock_client.return_value.messages.create.return_value = _mock_claude("Great application!")
    _, main_module = temp_db
    client = make_client(main_module)
    response = client.post(
        "/applications/new",
        data={
            "company": "Acme Corp",
            "role_title": "ML Engineer",
            "date_applied": "2026-03-01",
            "status": "applied",
        },
        follow_redirects=False,
    )
    assert "flash_encouragement" in response.cookies


@patch("agents.wellbeing._client")
def test_applications_new_post_creates_record(mock_client, temp_db):
    mock_client.return_value.messages.create.return_value = _mock_claude()
    db, main_module = temp_db
    client = make_client(main_module)
    client.post(
        "/applications/new",
        data={
            "company": "Cohere",
            "role_title": "Research Engineer",
            "date_applied": "2026-03-10",
            "status": "applied",
        },
    )
    response = client.get("/applications")
    assert "Cohere" in response.text


@patch("agents.wellbeing._client")
def test_applications_list_shows_toast_from_cookie(mock_client, temp_db):
    mock_client.return_value.messages.create.return_value = _mock_claude()
    _, main_module = temp_db
    client = make_client(main_module)
    client.cookies.set("flash_encouragement", "You did great!")
    response = client.get("/applications")
    assert "You did great!" in response.text


@patch("agents.wellbeing._client")
def test_applications_list_sends_delete_cookie_header(mock_client, temp_db):
    mock_client.return_value.messages.create.return_value = _mock_claude()
    _, main_module = temp_db
    client = make_client(main_module)
    client.cookies.set("flash_encouragement", "You did great!")
    response = client.get("/applications")
    # Server should respond with a Set-Cookie header that expires the cookie
    set_cookie = response.headers.get("set-cookie", "")
    assert "flash_encouragement" in set_cookie
    assert "max-age=0" in set_cookie.lower()


def test_applications_show_all_returns_200(temp_db):
    _, main_module = temp_db
    client = make_client(main_module)
    response = client.get("/applications?show_all=1")
    assert response.status_code == 200


def test_applications_update_status(temp_db):
    db, main_module = temp_db
    init_db(db)
    app_id = add_application(db, ApplicationIn(
        company="Test Co", role_title="Engineer",
        date_applied="2026-01-01", status="applied"
    ))
    client = make_client(main_module)
    response = client.post(
        f"/applications/{app_id}/status",
        data={"status": "interview"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    updated = get_application(db, app_id)
    assert updated.status == "interview"


def test_applications_delete(temp_db):
    db, main_module = temp_db
    init_db(db)
    app_id = add_application(db, ApplicationIn(
        company="Delete Me", role_title="Engineer",
        date_applied="2026-01-01", status="applied"
    ))
    client = make_client(main_module)
    response = client.post(
        f"/applications/{app_id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert get_application(db, app_id) is None
