"""Role suggestion agent — reads master CV and suggests target job roles."""

import json
from dataclasses import dataclass

import anthropic


@dataclass
class RoleSuggestion:
    title: str
    bullets: list[str]
    fit_level: str  # "obvious" | "adjacent" | "stretch"


def suggest_roles(cv_text: str) -> list[RoleSuggestion]:
    """
    Call Claude to suggest 6-8 job roles based on the candidate's CV.

    Args:
        cv_text: Raw CV content (YAML or plain text) as a string.

    Returns:
        List of RoleSuggestion dataclasses ordered from most to least obvious fit.
    """
    client = anthropic.Anthropic()

    prompt = f"""You are a career coach reviewing a candidate's CV. Suggest 6-8 job roles this person could realistically target.

Rules:
- Give specific role titles (e.g. "Senior ML Engineer", not just "Engineer")
- Write 2–3 bullet points per role grounding the fit in concrete CV evidence — cite actual roles, projects, skills, or years of experience by name
- Classify each role's fit as exactly one of: "obvious" (direct match to current experience), "adjacent" (strong transferable fit — different angle on their skills), or "stretch" (aspirational but supported by evidence)
- Include at least 2 "adjacent" or "stretch" roles the person may not have considered
- Do not invent or assume skills not present in the CV

Respond as a JSON array only, with this exact structure:
[
  {{
    "title": "Role Title",
    "bullets": ["specific evidence bullet 1", "specific evidence bullet 2"],
    "fit_level": "obvious"
  }}
]

CV:
{cv_text}

Return only the JSON array. No preamble, no explanation."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    data = json.loads(raw)
    return [
        RoleSuggestion(
            title=item["title"],
            bullets=item["bullets"],
            fit_level=item["fit_level"],
        )
        for item in data
    ]
