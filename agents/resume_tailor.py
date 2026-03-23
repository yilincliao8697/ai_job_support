import json
import os
from dataclasses import dataclass, field

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences from a string if present."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


@dataclass
class TailoredCV:
    """A CV tailored to a specific job description."""
    personal: dict
    experience: list[dict]
    projects: list[dict]
    education: list[dict]
    skills: dict
    target_role: str
    target_company: str


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def tailor_cv(cv_text: str, job_description: str) -> TailoredCV:
    """
    Takes the full CV as text and a job description.

    Claude selects relevant experience and projects, prioritises sections,
    rewrites bullet points to mirror JD language, and returns a TailoredCV.
    Respects a one-page constraint where possible.
    Uses claude-sonnet-4-6.
    """
    prompt = f"""You are an expert resume writer. Given a candidate's full CV and a job description, produce a tailored resume.

INSTRUCTIONS:
- Select the 2-3 most relevant experience entries
- Select 1-2 most relevant projects
- Rewrite bullet points to mirror the language and keywords in the job description
- Keep bullets concise and impact-focused (start with strong action verbs)
- Aim for a one-page resume where possible
- Extract the target role title and company name from the job description
- Return ONLY valid JSON matching the schema below — no markdown, no explanation

OUTPUT SCHEMA:
{{
  "personal": {{
    "name": "string",
    "email": "string",
    "location": "string",
    "linkedin": "string",
    "github": "string",
    "summary": "string (rewritten to target this specific role)"
  }},
  "experience": [
    {{
      "company": "string",
      "role": "string",
      "start": "string",
      "end": "string",
      "bullets": ["string"]
    }}
  ],
  "projects": [
    {{
      "name": "string",
      "description": "string",
      "bullets": ["string"]
    }}
  ],
  "education": [
    {{
      "institution": "string",
      "degree": "string",
      "year": "string"
    }}
  ],
  "skills": {{
    "languages": ["string"],
    "frameworks": ["string"],
    "tools": ["string"],
    "other": ["string"]
  }},
  "target_role": "string (job title from the JD)",
  "target_company": "string (company name from the JD)"
}}

CANDIDATE CV:
{cv_text}

JOB DESCRIPTION:
{job_description}
"""

    message = _client().messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = _strip_code_fences(message.content[0].text)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude returned invalid JSON: {e}\nRaw response:\n{raw}") from e

    required_keys = {"personal", "experience", "projects", "education", "skills", "target_role", "target_company"}
    missing = required_keys - data.keys()
    if missing:
        raise ValueError(f"Claude response missing required fields: {missing}")

    return TailoredCV(
        personal=data["personal"],
        experience=data["experience"],
        projects=data["projects"],
        education=data["education"],
        skills=data["skills"],
        target_role=data["target_role"],
        target_company=data["target_company"],
    )
