import yaml
from pathlib import Path


def load_cv(cv_path: str) -> dict:
    """Load and return master_cv.yaml as a dict."""
    path = Path(cv_path)
    if not path.exists():
        raise FileNotFoundError(f"CV file not found: {cv_path}")
    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_cv_as_text(cv_path: str) -> str:
    """
    Return a plain text representation of the CV suitable for passing to Claude.
    Includes all sections with clear headings.
    """
    cv = load_cv(cv_path)
    lines = []

    personal = cv.get("personal", {})
    lines.append("=== PERSONAL ===")
    lines.append(f"Name: {personal.get('name', '')}")
    lines.append(f"Email: {personal.get('email', '')}")
    lines.append(f"Location: {personal.get('location', '')}")
    lines.append(f"LinkedIn: {personal.get('linkedin', '')}")
    lines.append(f"GitHub: {personal.get('github', '')}")
    if personal.get("summary"):
        lines.append(f"Summary: {personal['summary']}")

    lines.append("\n=== EXPERIENCE ===")
    for exp in cv.get("experience", []):
        lines.append(f"\n{exp.get('role', '')} at {exp.get('company', '')} ({exp.get('start', '')} – {exp.get('end', '')})")
        lines.append(f"Tags: {', '.join(exp.get('tags', []))}")
        for bullet in exp.get("bullets", []):
            lines.append(f"  • {bullet}")

    lines.append("\n=== PROJECTS ===")
    for proj in cv.get("projects", []):
        lines.append(f"\n{proj.get('name', '')}: {proj.get('description', '')}")
        lines.append(f"Tags: {', '.join(proj.get('tags', []))}")
        for bullet in proj.get("bullets", []):
            lines.append(f"  • {bullet}")

    lines.append("\n=== EDUCATION ===")
    for edu in cv.get("education", []):
        lines.append(f"{edu.get('degree', '')} — {edu.get('institution', '')} ({edu.get('year', '')})")

    skills = cv.get("skills", {})
    lines.append("\n=== SKILLS ===")
    if skills.get("languages"):
        lines.append(f"Languages: {', '.join(skills['languages'])}")
    if skills.get("frameworks"):
        lines.append(f"Frameworks: {', '.join(skills['frameworks'])}")
    if skills.get("tools"):
        lines.append(f"Tools: {', '.join(skills['tools'])}")
    if skills.get("other"):
        lines.append(f"Other: {', '.join(skills['other'])}")

    return "\n".join(lines)
