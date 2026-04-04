import sqlite3
from datetime import datetime
from typing import Optional


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_pipelines_table(db_path: str) -> None:
    """Create the pipelines table if it does not exist. Safe to call on every startup."""
    with _connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pipelines (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                stage                INTEGER NOT NULL DEFAULT 1,
                max_stage            INTEGER NOT NULL DEFAULT 1,
                job_title            TEXT NOT NULL DEFAULT '',
                company              TEXT NOT NULL DEFAULT '',
                jd_text              TEXT NOT NULL DEFAULT '',
                resume_id            INTEGER,
                cover_letter_id      INTEGER,
                application_id       INTEGER,
                skipped_cover_letter INTEGER NOT NULL DEFAULT 0,
                created_at           TEXT NOT NULL,
                completed_at         TEXT
            )
        """)


def migrate_pipelines(db_path: str) -> None:
    """Add max_stage column if it doesn't exist (idempotent)."""
    with _connect(db_path) as conn:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(pipelines)").fetchall()}
        if "max_stage" not in cols:
            conn.execute("ALTER TABLE pipelines ADD COLUMN max_stage INTEGER NOT NULL DEFAULT 1")


def create_pipeline(db_path: str) -> int:
    """Create a new pipeline at stage 1 and return its id."""
    created_at = datetime.now().isoformat()
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO pipelines (created_at) VALUES (?)",
            (created_at,),
        )
        return cursor.lastrowid


def get_pipeline(db_path: str, pipeline_id: int) -> Optional[dict]:
    """Return a pipeline record as a dict, or None if not found."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM pipelines WHERE id = ?", (pipeline_id,)
        ).fetchone()
    return dict(row) if row else None


def update_pipeline(db_path: str, pipeline_id: int, **fields) -> None:
    """
    Update one or more fields on a pipeline record.

    Usage: update_pipeline(db_path, 1, stage=2, job_title="ML Engineer")
    Only the provided keyword arguments are updated.
    """
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [pipeline_id]
    with _connect(db_path) as conn:
        conn.execute(
            f"UPDATE pipelines SET {set_clause} WHERE id = ?", values
        )


def advance_pipeline_stage(db_path: str, pipeline_id: int, new_stage: int, **extra_fields) -> None:
    """
    Advance to new_stage and bump max_stage if new_stage is higher.
    Use this instead of update_pipeline when moving forward through the flow.
    """
    pipeline = get_pipeline(db_path, pipeline_id)
    if pipeline is None:
        return
    new_max = max(pipeline.get("max_stage") or 1, new_stage)
    update_pipeline(db_path, pipeline_id, stage=new_stage, max_stage=new_max, **extra_fields)


def list_active_pipelines(db_path: str) -> list[dict]:
    """Return all pipelines not yet completed, newest first."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM pipelines WHERE completed_at IS NULL ORDER BY created_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def complete_pipeline(db_path: str, pipeline_id: int, application_id: int) -> None:
    """Mark a pipeline as complete and record the resulting application id."""
    completed_at = datetime.now().isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE pipelines SET completed_at = ?, application_id = ? WHERE id = ?",
            (completed_at, application_id, pipeline_id),
        )


def delete_pipeline(db_path: str, pipeline_id: int) -> None:
    """Delete a pipeline record by id."""
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM pipelines WHERE id = ?", (pipeline_id,))
