import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"

TONES = {
    "professional": "Professional",
    "warm": "Warm",
    "enthusiastic": "Enthusiastic",
}


def generate_cover_letter(
    job_description: str,
    cv_text: str,
    tone: str = "professional",
    personal_note: str = "",
) -> str:
    """
    Generate a tailored cover letter using Claude.

    Args:
        job_description: The full job description text.
        cv_text: Master CV as plain text (from get_cv_as_text).
        tone: One of the TONES keys.
        personal_note: Optional extra context from the user (e.g. "I know someone there").

    Returns:
        Cover letter as plain text, ready to copy or edit.
    """
    tone_instructions = {
        "professional": "Formal and concise. Confident but not flashy. Every sentence earns its place.",
        "warm": "Friendly and personal. Reads like a human wrote it, not a template. First-person, direct.",
        "enthusiastic": "Energetic and forward-leaning. Genuine excitement for the role and company. Not over the top.",
    }
    tone_instruction = tone_instructions.get(tone, tone_instructions["professional"])

    personal_section = ""
    if personal_note.strip():
        personal_section = f"\nAdditional context from the applicant: {personal_note.strip()}\n"

    prompt = f"""You are writing a cover letter for a job application.

The applicant's background (from their CV):
{cv_text}
{personal_section}
Job description:
{job_description}

Write a cover letter with exactly three paragraphs:
1. Opening — hook that connects the applicant's background to this specific role. No "I am writing to apply for..." openers.
2. Evidence — 2–3 specific examples from the CV that are directly relevant to the JD. Be concrete.
3. Close — brief, forward-looking. Express genuine interest and invite next steps.

Tone: {tone_instruction}

Rules:
- Address to "Dear Hiring Team," (no specific name unless it appears in the JD)
- Only reference experience that appears in the CV — never invent or embellish
- No bullet points — flowing paragraphs only
- No "I am excited to" or "I am passionate about" clichés
- No sign-off or signature line — end after the closing paragraph
- Output the cover letter text only. No commentary."""

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    message = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()
