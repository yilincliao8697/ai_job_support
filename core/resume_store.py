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


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_resumes_table(db_path: str) -> None:
    """Create the resumes table if it does not exist. Safe to call on every startup."""
    with _connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS resumes (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                filename       TEXT NOT NULL,
                company        TEXT NOT NULL,
                role           TEXT NOT NULL,
                generated_at   TEXT NOT NULL,
                application_id INTEGER
            )
        """)


def record_resume(db_path: str, filename: str, company: str, role: str) -> int:
    """Insert a new resume record and return its id."""
    generated_at = datetime.now().isoformat()
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO resumes (filename, company, role, generated_at) VALUES (?, ?, ?, ?)",
            (filename, company, role, generated_at),
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


def link_application(db_path: str, resume_id: int, application_id: int) -> None:
    """Set the application_id FK on a resume record."""
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE resumes SET application_id = ? WHERE id = ?",
            (application_id, resume_id),
        )


def delete_resume_record(db_path: str, resume_id: int) -> None:
    """Delete the resume DB record. Does not delete the PDF file."""
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM resumes WHERE id = ?", (resume_id,))
