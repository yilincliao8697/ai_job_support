import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class CoverLetterRecord:
    """A saved cover letter."""
    id: int
    job_title: str
    company: str
    content: str
    tone: str
    created_at: str
    application_id: Optional[int] = None


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_cover_letters_table(db_path: str) -> None:
    """Create the cover_letters table if it does not exist. Safe to call on every startup."""
    with _connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cover_letters (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                job_title       TEXT NOT NULL DEFAULT '',
                company         TEXT NOT NULL DEFAULT '',
                content         TEXT NOT NULL,
                tone            TEXT NOT NULL DEFAULT 'professional',
                created_at      TEXT NOT NULL,
                application_id  INTEGER
            )
        """)


def save_cover_letter(
    db_path: str,
    content: str,
    tone: str,
    job_title: str = "",
    company: str = "",
    application_id: Optional[int] = None,
) -> int:
    """Insert a new cover letter record and return its id."""
    created_at = datetime.now().isoformat()
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO cover_letters (job_title, company, content, tone, created_at, application_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (job_title, company, content, tone, created_at, application_id),
        )
        return cursor.lastrowid


def get_cover_letter(db_path: str, cover_letter_id: int) -> Optional[CoverLetterRecord]:
    """Return a single cover letter record by id, or None if not found."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM cover_letters WHERE id = ?", (cover_letter_id,)
        ).fetchone()
    if row is None:
        return None
    return CoverLetterRecord(**dict(row))


def list_cover_letters(db_path: str) -> list[CoverLetterRecord]:
    """Return all cover letter records, newest first."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM cover_letters ORDER BY created_at DESC"
        ).fetchall()
    return [CoverLetterRecord(**dict(row)) for row in rows]


def delete_cover_letter(db_path: str, cover_letter_id: int) -> None:
    """Delete a cover letter record by id."""
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM cover_letters WHERE id = ?", (cover_letter_id,))
