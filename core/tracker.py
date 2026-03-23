import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, date


@dataclass
class ApplicationIn:
    """Data required to create a new application."""
    company: str
    role_title: str
    date_applied: str
    status: str
    job_url: str = ""
    notes: str = ""
    resume_filename: str = ""
    referral_contacts: str = ""


@dataclass
class Application(ApplicationIn):
    """A persisted application record."""
    id: int = 0
    created_at: str = ""


@dataclass
class ApplicationUpdate:
    """Partial update fields for an application."""
    company: str | None = None
    role_title: str | None = None
    job_url: str | None = None
    date_applied: str | None = None
    status: str | None = None
    notes: str | None = None
    resume_filename: str | None = None
    referral_contacts: str | None = None


ACTIVE_STATUSES = ("applied", "phone_screen", "interview")


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    """Create the applications and watchlist tables if they don't exist."""
    with _connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                company           TEXT NOT NULL,
                role_title        TEXT NOT NULL,
                job_url           TEXT DEFAULT '',
                date_applied      TEXT NOT NULL,
                status            TEXT NOT NULL,
                notes             TEXT DEFAULT '',
                resume_filename   TEXT DEFAULT '',
                referral_contacts TEXT DEFAULT '',
                created_at        TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name     TEXT NOT NULL UNIQUE,
                notes            TEXT DEFAULT '',
                added_at         TEXT NOT NULL,
                pulse_json       TEXT,
                pulse_updated_at TEXT,
                sector           TEXT,
                website_url      TEXT,
                careers_url      TEXT
            )
        """)


def add_application(db_path: str, application: ApplicationIn) -> int:
    """Insert a new application and return its id."""
    created_at = datetime.now().isoformat()
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO applications
                (company, role_title, job_url, date_applied, status,
                 notes, resume_filename, referral_contacts, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                application.company,
                application.role_title,
                application.job_url,
                application.date_applied,
                application.status,
                application.notes,
                application.resume_filename,
                application.referral_contacts,
                created_at,
            ),
        )
        return cursor.lastrowid


def get_application(db_path: str, application_id: int) -> Application | None:
    """Retrieve a single application by id, or None if not found."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
    if row is None:
        return None
    return Application(**dict(row))


def list_applications(db_path: str, active_only: bool = True) -> list[Application]:
    """Return all applications, optionally filtered to active statuses only."""
    with _connect(db_path) as conn:
        if active_only:
            placeholders = ",".join("?" * len(ACTIVE_STATUSES))
            rows = conn.execute(
                f"SELECT * FROM applications WHERE status IN ({placeholders}) ORDER BY date_applied DESC",
                ACTIVE_STATUSES,
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM applications ORDER BY date_applied DESC"
            ).fetchall()
    return [Application(**dict(row)) for row in rows]


def update_status(db_path: str, application_id: int, status: str) -> None:
    """Update the status of an application."""
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE applications SET status = ? WHERE id = ?",
            (status, application_id),
        )


def update_application(db_path: str, application_id: int, updates: ApplicationUpdate) -> None:
    """Apply a partial update to an application record."""
    fields = {k: v for k, v in updates.__dict__.items() if v is not None}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [application_id]
    with _connect(db_path) as conn:
        conn.execute(
            f"UPDATE applications SET {set_clause} WHERE id = ?", values
        )


def delete_application(db_path: str, application_id: int) -> None:
    """Delete an application by id."""
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM applications WHERE id = ?", (application_id,))


def get_application_counts_by_date(db_path: str) -> list[dict]:
    """
    Return cumulative application counts by date for the effort chart.
    Returns a list of {date, cumulative_count} dicts ordered by date.
    """
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT date_applied, COUNT(*) as count FROM applications GROUP BY date_applied ORDER BY date_applied"
        ).fetchall()

    cumulative = 0
    result = []
    for row in rows:
        cumulative += row["count"]
        result.append({"date": row["date_applied"], "cumulative_count": cumulative})
    return result
