import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-haiku-4-5-20251001"


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def get_encouragement_on_log(company: str, role_title: str, user_background: str) -> str:
    """
    Generate a short encouragement message when a new application is logged.

    Validates the effort and the fit. Does not suggest next steps or other roles.
    2-3 sentences. Warm but not generic. No emojis.
    """
    prompt = (
        f"The user just applied for a {role_title} role at {company}. "
        f"Their background: {user_background}. "
        "Write a short (2-3 sentence) warm message that validates this application. "
        "Reference the company and role, and mention one concrete reason from their background "
        "why this is a good match. "
        "Do not suggest other roles, next steps, or what they should do next — "
        "sending an application is hard work and deserves acknowledgement on its own. "
        "Be genuine. No emojis."
    )
    message = _client().messages.create(
        model=MODEL,
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def get_reframe_on_hard_status(company: str, role_title: str, status: str) -> str:
    """
    Generate a brief, grounded reframe when an application is marked rejected or ghosted.

    Honest perspective, not cheerleading. 2-3 sentences.
    """
    prompt = (
        f"The user's application for {role_title} at {company} has been marked as '{status}'. "
        "Write a brief (2-3 sentence) grounded reframe. "
        "Be honest and real — not toxic positivity, not dismissive. "
        "Help them see this in perspective without minimising their feelings. No emojis."
    )
    message = _client().messages.create(
        model=MODEL,
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def get_one_thing_today(active_applications: list[dict], watchlist: list[dict]) -> str:
    """
    Suggest a single action based on the current state of applications and watchlist.

    Returns a plain string suggestion, e.g.:
    "You haven't applied anywhere this week — want to expand your watchlist?"
    """
    apps_summary = f"{len(active_applications)} active applications"
    watchlist_summary = f"{len(watchlist)} companies on watchlist"

    prompt = (
        f"A job seeker has {apps_summary} and {watchlist_summary}. "
        "Suggest ONE specific, actionable thing they could do today to move their job search forward. "
        "Keep it to one sentence. Be direct and practical. No emojis."
    )
    message = _client().messages.create(
        model=MODEL,
        max_tokens=80,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def get_on_demand_encouragement(user_message: str = "") -> str:
    """
    Generate encouragement on demand from the /encouragement page.

    If user_message is provided, give a contextual response.
    If empty, return a general supportive message.
    """
    if user_message.strip():
        prompt = (
            f"A job seeker says: \"{user_message}\". "
            "Respond with 3-4 sentences of genuine, grounded support. "
            "Acknowledge what they said. Be warm but real. No toxic positivity. No emojis."
        )
    else:
        prompt = (
            "A job seeker needs encouragement. Write 3-4 sentences of genuine, warm support "
            "for someone in the middle of a job search. Be real and human. No emojis."
        )
    message = _client().messages.create(
        model=MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()
