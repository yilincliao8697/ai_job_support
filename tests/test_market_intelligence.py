import json
import pytest
from unittest.mock import patch, MagicMock
from agents.market_intelligence import expand_companies, get_company_pulse, SimilarCompany, CompanyPulse

SAMPLE_JD = "We are hiring an ML Engineer at Cohere to work on LLM infrastructure."

VALID_EXPANDER_RESPONSE = json.dumps([
    {"name": "Mistral AI", "reason": "Series A, LLM focus, similar eng team size", "sector": "LLM Tooling"},
    {"name": "Together AI", "reason": "Series B, LLM infra, open-source focus", "sector": "LLM Tooling"},
    {"name": "Anyscale", "reason": "Series C, distributed ML, Python-heavy", "sector": "Infra"},
])

VALID_PULSE_RESPONSE = json.dumps({
    "recent_funding": "Series B, $50M, Oct 2025, led by Sequoia",
    "headcount_direction": "Engineering team grew 25% over last 12 months",
    "layoff_news": "No layoff news found",
    "open_roles_count": "12 AI/ML roles currently posted",
    "hiring_signal": "Post-Series B + active hiring = strong hiring window",
    "sources": ["https://techcrunch.com/cohere", "https://linkedin.com/company/cohere"],
})


def _mock_response(text: str):
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


# ---------------------------------------------------------------------------
# Company Expander
# ---------------------------------------------------------------------------

@patch("agents.market_intelligence._client")
def test_expand_companies_returns_list_of_similar_companies(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response(VALID_EXPANDER_RESPONSE)
    result = expand_companies(SAMPLE_JD)
    assert isinstance(result, list)
    assert all(isinstance(c, SimilarCompany) for c in result)


@patch("agents.market_intelligence._client")
def test_expand_companies_returns_between_1_and_10(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response(VALID_EXPANDER_RESPONSE)
    result = expand_companies(SAMPLE_JD)
    assert 1 <= len(result) <= 10


@patch("agents.market_intelligence._client")
def test_expand_companies_entries_have_name_and_reason(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response(VALID_EXPANDER_RESPONSE)
    result = expand_companies(SAMPLE_JD)
    for company in result:
        assert company.name
        assert company.reason


@patch("agents.market_intelligence._client")
def test_expand_companies_raises_on_invalid_json(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response("not json")
    with pytest.raises(ValueError, match="invalid JSON"):
        expand_companies(SAMPLE_JD)


@patch("agents.market_intelligence._client")
def test_expand_companies_raises_if_not_list(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response('{"name": "Foo"}')
    with pytest.raises(ValueError, match="JSON list"):
        expand_companies(SAMPLE_JD)


@patch("agents.market_intelligence._client")
def test_expand_companies_returns_sector(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response(VALID_EXPANDER_RESPONSE)
    result = expand_companies(SAMPLE_JD)
    assert result[0].sector == "LLM Tooling"
    assert result[2].sector == "Infra"


@patch("agents.market_intelligence._client")
def test_expand_companies_handles_missing_sector(mock_client):
    no_sector = json.dumps([
        {"name": "Mistral AI", "reason": "LLM focus"},
    ])
    mock_client.return_value.messages.create.return_value = _mock_response(no_sector)
    result = expand_companies(SAMPLE_JD)
    assert result[0].sector is None


# ---------------------------------------------------------------------------
# Company Pulse
# ---------------------------------------------------------------------------

@patch("agents.market_intelligence._client")
def test_get_company_pulse_returns_pulse_instance(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response(VALID_PULSE_RESPONSE)
    result = get_company_pulse("Cohere")
    assert isinstance(result, CompanyPulse)


@patch("agents.market_intelligence._client")
def test_get_company_pulse_all_fields_nonempty(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response(VALID_PULSE_RESPONSE)
    result = get_company_pulse("Cohere")
    assert result.recent_funding
    assert result.headcount_direction
    assert result.layoff_news
    assert result.open_roles_count
    assert result.hiring_signal


@patch("agents.market_intelligence._client")
def test_get_company_pulse_sources_is_list(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response(VALID_PULSE_RESPONSE)
    result = get_company_pulse("Cohere")
    assert isinstance(result.sources, list)


@patch("agents.market_intelligence._client")
def test_get_company_pulse_raises_on_invalid_json(mock_client):
    mock_client.return_value.messages.create.return_value = _mock_response("not json")
    with pytest.raises(ValueError, match="invalid JSON"):
        get_company_pulse("Cohere")


@patch("agents.market_intelligence._client")
def test_get_company_pulse_raises_on_missing_fields(mock_client):
    incomplete = json.dumps({"recent_funding": "Series B"})
    mock_client.return_value.messages.create.return_value = _mock_response(incomplete)
    with pytest.raises(ValueError, match="missing required fields"):
        get_company_pulse("Cohere")
