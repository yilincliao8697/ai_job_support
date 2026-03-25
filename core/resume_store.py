import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ResumeRecord:
    """A record of a generated resume PDF."""
    id: int
    filename: str
    company: str
    role: str
    generated_at: str
    application_id: Optional[int] = None
    job_description: Optional[str] = None
    parent_id: Optional[int] = None
    feedback_summary: Optional[str] = None
    tailored_json: Optional[str] = None


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_resumes_table(db_path: str) -> None:
    """Create the resumes table if it does not exist. Safe to call on every startup."""
    with _connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS resumes (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                filename         TEXT NOT NULL,
                company          TEXT NOT NULL,
                role             TEXT NOT NULL,
                generated_at     TEXT NOT NULL,
                application_id   INTEGER,
                job_description  TEXT,
                parent_id        INTEGER,
                feedback_summary TEXT
            )
        """)


def migrate_resumes(db_path: str) -> None:
    """Add revision columns and tailored_json to the resumes table if they don't exist (idempotent)."""
    new_cols = {
        "job_description": "TEXT",
        "parent_id": "INTEGER",
        "feedback_summary": "TEXT",
        "tailored_json": "TEXT",
    }
    with _connect(db_path) as conn:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(resumes)").fetchall()}
        for col, col_type in new_cols.items():
            if col not in cols:
                conn.execute(f"ALTER TABLE resumes ADD COLUMN {col} {col_type}")


def record_resume(
    db_path: str,
    filename: str,
    company: str,
    role: str,
    job_description: Optional[str] = None,
    parent_id: Optional[int] = None,
    feedback_summary: Optional[str] = None,
    tailored_json: Optional[str] = None,
) -> int:
    """Insert a new resume record and return its id."""
    generated_at = datetime.now().isoformat()
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO resumes
               (filename, company, role, generated_at, job_description, parent_id, feedback_summary, tailored_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (filename, company, role, generated_at, job_description, parent_id, feedback_summary, tailored_json),
        )
        return cursor.lastrowid


def list_resumes(db_path: str) -> list[ResumeRecord]:
    """Return all resume records, newest first."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM resumes ORDER BY generated_at DESC"
        ).fetchall()
    return [ResumeRecord(**dict(row)) for row in rows]


def get_resume(db_path: str, resume_id: int) -> Optional[ResumeRecord]:
    """Return a single resume record by id, or None if not found."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM resumes WHERE id = ?", (resume_id,)
        ).fetchone()
    if row is None:
        return None
    return ResumeRecord(**dict(row))


def get_revision_chain(db_path: str, resume_id: int) -> list[ResumeRecord]:
    """
    Walk parent_id links from the given record back to the root.
    Returns the chain oldest-first (root at index 0, given record last).
    Returns a single-item list if the record has no parent.
    """
    chain = []
    current_id = resume_id
    while current_id is not None:
        record = get_resume(db_path, current_id)
        if record is None:
            break
        chain.append(record)
        current_id = record.parent_id
    chain.reverse()
    return chain


def link_application(db_path: str, resume_id: int, application_id: int) -> None:
    """Set the application_id FK on a resume record."""
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE resumes SET application_id = ? WHERE id = ?",
            (application_id, resume_id),
        )


def update_resume_json(db_path: str, resume_id: int, tailored_json: str) -> None:
    """Overwrite the tailored_json field for an existing resume record."""
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE resumes SET tailored_json = ? WHERE id = ?",
            (tailored_json, resume_id),
        )


def update_resume_after_edit(
    db_path: str,
    resume_id: int,
    tailored_json: str,
    filename: str,
) -> None:
    """Update tailored_json and filename after a live edit re-render."""
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE resumes SET tailored_json = ?, filename = ? WHERE id = ?",
            (tailored_json, filename, resume_id),
        )


def get_tailored_cv(db_path: str, resume_id: int) -> Optional[dict]:
    """
    Return the parsed tailored_json dict for a resume record, or None if
    the record does not exist or has no stored JSON.
    """
    import json
    record = get_resume(db_path, resume_id)
    if record is None or record.tailored_json is None:
        return None
    return json.loads(record.tailored_json)


def delete_resume_record(db_path: str, resume_id: int) -> None:
    """Delete the resume DB record. Does not delete the PDF file."""
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM resumes WHERE id = ?", (resume_id,))
