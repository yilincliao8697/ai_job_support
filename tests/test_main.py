from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from web.main import app

client = TestClient(app)


def _mock_claude(text="Keep going."):
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


@patch("agents.wellbeing._client")
def test_dashboard_returns_200(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_claude()
    response = client.get("/")
    assert response.status_code == 200


@patch("agents.wellbeing._client")
def test_dashboard_contains_app_name(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_claude()
    response = client.get("/")
    assert "AI Job Support" in response.text
