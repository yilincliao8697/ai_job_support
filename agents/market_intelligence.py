import json
import os
from dataclasses import dataclass, field

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"


@dataclass
class SimilarCompany:
    """A company similar to the one in the job posting."""
    name: str
    reason: str


@dataclass
class CompanyPulse:
    """A structured summary of a target company from live web data."""
    company_name: str
    recent_funding: str
    headcount_direction: str
    layoff_news: str
    open_roles_count: str
    hiring_signal: str
    sources: list[str] = field(default_factory=list)


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def expand_companies(job_description: str) -> list[SimilarCompany]:
    """
    Analyze a job posting and return 5-10 similar companies the user may not have considered.

    Claude analyzes company stage, tech stack, domain, and team size from the JD.
    Returns a structured list of SimilarCompany instances.
    Uses claude-sonnet-4-6.
    """
    prompt = f"""Analyze this job posting and identify 5-10 similar companies the candidate should consider applying to.

Focus on: company stage, tech stack, domain, and team size. Return companies the candidate may not have thought of.

Return ONLY valid JSON — no markdown, no explanation:
[
  {{"name": "Company Name", "reason": "One line: stage, domain focus, why similar"}},
  ...
]

JOB POSTING:
{job_description}
"""
    message = _client().messages.create(
        model=MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude returned invalid JSON: {e}\nRaw: {raw}") from e

    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list, got: {type(data)}")

    return [SimilarCompany(name=item["name"], reason=item["reason"]) for item in data]


def get_company_pulse(company_name: str) -> CompanyPulse:
    """
    Synthesize a structured company summary from live web data.

    Uses Claude's web_search tool to gather current information.
    Returns a populated CompanyPulse instance.
    Uses claude-sonnet-4-6 with web_search tool.
    """
    prompt = f"""Research {company_name} and provide a structured summary for a job seeker evaluating whether to apply.

Use web search to find current information. Then return ONLY valid JSON — no markdown, no explanation:
{{
  "recent_funding": "Round size, date, investors, stage — or 'No recent funding found'",
  "headcount_direction": "Engineering team growth or shrinkage over last 6-12 months",
  "layoff_news": "Any recent layoffs — or 'No layoff news found'",
  "open_roles_count": "How many AI/ML/engineering roles are currently posted",
  "hiring_signal": "One line assessment e.g. 'Post-Series B + active hiring = strong window'",
  "sources": ["url1", "url2"]
}}
"""
    tools = [
        {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 5,
        }
    ]

    message = _client().messages.create(
        model=MODEL,
        max_tokens=1500,
        tools=tools,
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract the final text response (Claude may have made tool calls before this)
    raw = ""
    for block in message.content:
        if hasattr(block, "text"):
            raw = block.text.strip()

    if not raw:
        raise ValueError("Claude returned no text response after web search")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude returned invalid JSON: {e}\nRaw: {raw}") from e

    required = {"recent_funding", "headcount_direction", "layoff_news", "open_roles_count", "hiring_signal"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Claude response missing required fields: {missing}")

    return CompanyPulse(
        company_name=company_name,
        recent_funding=data["recent_funding"],
        headcount_direction=data["headcount_direction"],
        layoff_news=data["layoff_news"],
        open_roles_count=data["open_roles_count"],
        hiring_signal=data["hiring_signal"],
        sources=data.get("sources", []),
    )
