import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class WatchlistCompany:
    """A company on the target watchlist."""
    id: int
    company_name: str
    notes: str
    added_at: str
    pulse_json: Optional[str] = None
    pulse_updated_at: Optional[str] = None


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def migrate_watchlist(db_path: str) -> None:
    """Add pulse columns to watchlist table if they don't exist (idempotent)."""
    with _connect(db_path) as conn:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(watchlist)").fetchall()}
        if "pulse_json" not in cols:
            conn.execute("ALTER TABLE watchlist ADD COLUMN pulse_json TEXT")
        if "pulse_updated_at" not in cols:
            conn.execute("ALTER TABLE watchlist ADD COLUMN pulse_updated_at TEXT")


def add_company(db_path: str, company_name: str, notes: str = "") -> int:
    """Add a company to the watchlist and return its id."""
    added_at = datetime.now().isoformat()
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO watchlist (company_name, notes, added_at) VALUES (?, ?, ?)",
            (company_name, notes, added_at),
        )
        return cursor.lastrowid


def list_companies(db_path: str) -> list[WatchlistCompany]:
    """Return all companies on the watchlist."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM watchlist ORDER BY added_at DESC"
        ).fetchall()
    return [WatchlistCompany(**dict(row)) for row in rows]


def remove_company(db_path: str, company_id: int) -> None:
    """Remove a company from the watchlist by id."""
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM watchlist WHERE id = ?", (company_id,))


def update_company_notes(db_path: str, company_id: int, notes: str) -> None:
    """Update the notes field for a watchlist company."""
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE watchlist SET notes = ? WHERE id = ?",
            (notes, company_id),
        )


def save_pulse(db_path: str, company_id: int, pulse_data: dict) -> None:
    """Persist a CompanyPulse result as JSON against a watchlist company."""
    updated_at = datetime.now().isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE watchlist SET pulse_json = ?, pulse_updated_at = ? WHERE id = ?",
            (json.dumps(pulse_data), updated_at, company_id),
        )


def load_pulse(db_path: str, company_id: int) -> Optional[dict]:
    """Load a cached CompanyPulse dict for a watchlist company, or None if not stored."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT pulse_json FROM watchlist WHERE id = ?", (company_id,)
        ).fetchone()
    if row and row["pulse_json"]:
        return json.loads(row["pulse_json"])
    return None
