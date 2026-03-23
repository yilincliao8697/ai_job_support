from unittest.mock import MagicMock, patch
import pytest
from agents.wellbeing import (
    get_encouragement_on_log,
    get_reframe_on_hard_status,
    get_one_thing_today,
    get_on_demand_encouragement,
)


def _mock_response(text: str):
    """Build a mock Anthropic messages response."""
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


@patch("agents.wellbeing._client")
def test_get_encouragement_on_log_returns_string(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response(
        "Great application! Your ML background is a strong fit for this role."
    )
    result = get_encouragement_on_log("Cohere", "ML Engineer", "ML engineer with 3 years experience")
    assert isinstance(result, str)
    assert len(result) > 0


@patch("agents.wellbeing._client")
def test_get_reframe_on_hard_status_rejected(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response(
        "Rejection is part of the process. Keep going."
    )
    result = get_reframe_on_hard_status("Acme Corp", "Engineer", "rejected")
    assert isinstance(result, str)
    assert len(result) > 0


@patch("agents.wellbeing._client")
def test_get_reframe_on_hard_status_ghosted(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response(
        "Ghosting says more about their process than your worth."
    )
    result = get_reframe_on_hard_status("Startup X", "PM", "ghosted")
    assert isinstance(result, str)
    assert len(result) > 0


@patch("agents.wellbeing._client")
def test_get_one_thing_today_returns_string(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response(
        "Follow up on your application to Cohere — it's been a week."
    )
    result = get_one_thing_today(
        [{"company": "Cohere", "status": "applied"}],
        [{"company_name": "Mistral"}],
    )
    assert isinstance(result, str)
    assert len(result) > 0


@patch("agents.wellbeing._client")
def test_get_on_demand_encouragement_no_message(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response(
        "You're putting in real effort. That matters."
    )
    result = get_on_demand_encouragement()
    assert isinstance(result, str)
    assert len(result) > 0


@patch("agents.wellbeing._client")
def test_get_on_demand_encouragement_with_message(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response(
        "That sounds really tough. It's okay to feel that way."
    )
    result = get_on_demand_encouragement("I'm feeling really discouraged today.")
    assert isinstance(result, str)
    assert len(result) > 0
