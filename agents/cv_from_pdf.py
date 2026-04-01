import io
import os

import anthropic
import pypdf
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"


def extract_pdf_text(file_bytes: bytes) -> str:
    """Extract plain text from a PDF given its raw bytes."""
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def cv_yaml_from_pdf(pdf_text: str, example_schema: str) -> str:
    """
    Convert extracted CV text into YAML matching the app's master_cv schema.

    Args:
        pdf_text: Plain text extracted from the uploaded PDF.
        example_schema: Contents of master_cv.example.yaml as a formatting reference.

    Returns:
        A YAML string ready to write to master_cv.yaml.
    """
    prompt = (
        "You are converting a CV into a structured YAML file.\n\n"
        "Here is the CV content extracted from a PDF:\n"
        f"{pdf_text}\n\n"
        "Here is the YAML schema to follow exactly:\n"
        f"{example_schema}\n\n"
        "Convert the CV into YAML following this schema. Rules:\n"
        "- Output only valid YAML. No markdown fences, no explanation.\n"
        "- Use the exact same top-level keys as the schema.\n"
        "- Preserve the user's actual content — do not invent or embellish.\n"
        "- For fields not found in the CV, use an empty string or empty list.\n"
        "- For experience bullets, extract the most important 2–4 achievements per role.\n"
        "- For skills, infer from experience and projects if not listed explicitly.\n"
        "- Dates should be in YYYY-MM format where possible."
    )

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    message = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()
