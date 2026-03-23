import sqlite3
from dataclasses import dataclass
from datetime import datetime


@dataclass
class WatchlistCompany:
    """A company on the target watchlist."""
    id: int
    company_name: str
    notes: str
    added_at: str


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


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
