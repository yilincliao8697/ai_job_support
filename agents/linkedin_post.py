import os
import re
import httpx
import anthropic
from dotenv import load_dotenv
from core.cv_store import load_cv

load_dotenv()

MODEL = "claude-sonnet-4-6"

CATEGORIES = {
    "tech_tool": "Tech / Tool Experience",
    "industry_application": "Industry Application",
    "paper_blog": "Paper or Blog Reaction",
    "tip_howto": "Tip / How-To",
    "career_reflection": "Career Reflection",
}

TONES = {
    "insightful": "Insightful",
    "conversational": "Conversational",
    "hot_take": "Hot Take / Opinionated",
    "practical": "Practical",
    "reflective": "Reflective",
}

_TONE_INSTRUCTIONS = {
    "insightful": "Write with authority and depth. Share a non-obvious perspective or connect ideas in a way that makes the reader think.",
    "conversational": "Write like you're talking to a colleague. Warm, direct, first-person. A bit informal.",
    "hot_take": "Take a clear, confident position. Don't hedge. It's okay if some people disagree — that's the point.",
    "practical": "Lead with the takeaway. Give the reader something they can actually use or apply.",
    "reflective": "Write from personal experience. What did you observe, learn, or come to believe? Be genuine.",
}


def get_linkedin_context(cv_path: str) -> str:
    """
    Extract a focused professional context from master_cv.yaml for use in post generation.
    Includes summary, recent experience, skills, and projects. Excludes contact info.
    """
    cv = load_cv(cv_path)
    lines = []

    personal = cv.get("personal", {})
    if personal.get("summary"):
        lines.append(f"Professional summary: {personal['summary']}")

    lines.append("\nRecent experience:")
    for exp in cv.get("experience", [])[:4]:
        lines.append(
            f"- {exp.get('role', '')} at {exp.get('company', '')} "
            f"({exp.get('start', '')}–{exp.get('end', '')})"
        )
        tags = exp.get("tags", [])
        if tags:
            lines.append(f"  Tags: {', '.join(tags)}")
        for bullet in exp.get("bullets", [])[:3]:
            lines.append(f"  • {bullet}")

    skills = cv.get("skills", {})
    skill_parts = []
    for key in ("languages", "frameworks", "tools", "other"):
        vals = skills.get(key, [])
        if vals:
            skill_parts.append(f"{key}: {', '.join(vals)}")
    if skill_parts:
        lines.append(f"\nSkills — {'; '.join(skill_parts)}")

    lines.append("\nProjects:")
    for proj in cv.get("projects", []):
        lines.append(f"- {proj.get('name', '')}: {proj.get('description', '')}")
        tags = proj.get("tags", [])
        if tags:
            lines.append(f"  Tags: {', '.join(tags)}")

    return "\n".join(lines)


def fetch_url_content(url: str) -> str:
    """
    Fetch a URL and return cleaned plain text (first ~4000 chars of article content).

    Strips scripts, styles, and nav boilerplate. Prefers <article> or <main> blocks
    over full-page content. Returns empty string on any error.
    """
    try:
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            html = response.text

        # Remove script, style, nav, header, footer blocks entirely (including their content)
        for tag in ("script", "style", "nav", "header", "footer", "aside"):
            html = re.sub(rf"<{tag}[\s>].*?</{tag}>", " ", html, flags=re.IGNORECASE | re.DOTALL)

        # Prefer <article> or <main> if present — much more likely to be the actual content
        for container in ("article", "main"):
            match = re.search(rf"<{container}[\s>](.*?)</{container}>", html, re.IGNORECASE | re.DOTALL)
            if match:
                html = match.group(1)
                break

        # Strip remaining HTML tags
        text = re.sub(r"<[^>]+>", " ", html)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text[:4000]
    except Exception:
        return ""


def generate_linkedin_posts(
    cv_context: str,
    category: str,
    topic: str,
    tone: str,
    url_content: str = "",
    count: int = 3,
) -> list[str]:
    """
    Generate LinkedIn posts tailored to the user's professional background.

    Args:
        cv_context: Professional context from get_linkedin_context()
        category: One of the CATEGORIES keys
        topic: Free-text description of what to post about
        tone: One of the TONES keys
        url_content: Cleaned text from a source URL, if provided
        count: Number of post variants to generate (default 3)

    Returns:
        List of post strings, each ~300 words in LinkedIn style.
    """
    category_label = CATEGORIES.get(category, category)
    tone_label = TONES.get(tone, tone)
    tone_instruction = _TONE_INSTRUCTIONS.get(tone, _TONE_INSTRUCTIONS["insightful"])

    source_section = ""
    if url_content:
        source_section = f"\nSource material (from the URL the user provided):\n{url_content}\n"

    topic_desc = topic if topic else "their general expertise and experience in this category"

    prompt = (
        f"You are helping a professional write LinkedIn posts to build their presence "
        f"and signal their expertise to recruiters.\n\n"
        f"Their professional background:\n{cv_context}\n"
        f"{source_section}\n"
        f"Today they want to post about: {category_label}\n"
        f"Topic / focus: {topic_desc}\n\n"
        f"Tone: {tone_label} — {tone_instruction}\n\n"
        f"Write {count} distinct LinkedIn post(s) on this topic. Each post should:\n"
        f"- Be approximately 300 words (200–400 is fine)\n"
        f"- Use LinkedIn's natural style: short paragraphs, line breaks between ideas, no walls of text\n"
        f"- Sound like a real person, sound polite, no harsh criticisms, sound interested but don't overdo enthusiasm\n"
        f"- Be grounded in the user's actual background — reference one thing from their experience where relevant\n"
        f"- Avoid generic advice that anyone could write\n"
        f"- No hashtags\n"
        f"- No emojis (unless tone is conversational or hot_take, in which case 1–2 max)\n"
        f"- No self-promotional fluff (\"I'm excited to share...\")\n\n"
        f"Separate each post with exactly this delimiter on its own line:\n---\n\n"
        f"Write only the posts. No introductions, no labels like \"Post 1:\", no commentary after."
    )

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    message = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    posts = [p.strip() for p in raw.split("---") if p.strip()]
    return posts[:count]


def regenerate_linkedin_post(
    cv_context: str,
    category: str,
    topic: str,
    tone: str,
    url_content: str = "",
) -> str:
    """
    Generate a single replacement LinkedIn post. Used by the 'Show me another' action.
    """
    posts = generate_linkedin_posts(cv_context, category, topic, tone, url_content, count=1)
    return posts[0] if posts else ""
