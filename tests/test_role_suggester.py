"""Tests for the role suggestion agent."""

from unittest.mock import MagicMock, patch

from agents.role_suggester import RoleSuggestion, suggest_roles

MOCK_RESPONSE = """[
  {
    "title": "Senior ML Engineer",
    "bullets": ["5 years Python and PyTorch", "Built 3 production ML pipelines"],
    "fit_level": "obvious"
  },
  {
    "title": "Technical Program Manager",
    "bullets": ["Led cross-functional team of 6", "Managed two product launches"],
    "fit_level": "adjacent"
  }
]"""


def test_suggest_roles_returns_list():
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=MOCK_RESPONSE)]

    with patch("agents.role_suggester.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = mock_message
        results = suggest_roles("dummy cv text")

    assert isinstance(results, list)
    assert len(results) == 2
    assert all(isinstance(r, RoleSuggestion) for r in results)


def test_suggest_roles_fields():
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=MOCK_RESPONSE)]

    with patch("agents.role_suggester.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = mock_message
        results = suggest_roles("dummy cv text")

    first = results[0]
    assert first.title == "Senior ML Engineer"
    assert len(first.bullets) == 2
    assert first.fit_level == "obvious"
