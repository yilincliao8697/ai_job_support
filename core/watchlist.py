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
    sector: Optional[str] = None
    website_url: Optional[str] = None
    careers_url: Optional[str] = None


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def migrate_watchlist(db_path: str) -> None:
    """Add optional columns to watchlist table if they don't exist (idempotent)."""
    with _connect(db_path) as conn:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(watchlist)").fetchall()}
        for col in ("pulse_json", "pulse_updated_at", "sector", "website_url", "careers_url"):
            if col not in cols:
                conn.execute(f"ALTER TABLE watchlist ADD COLUMN {col} TEXT")


def add_company(
    db_path: str,
    company_name: str,
    notes: str = "",
    sector: Optional[str] = None,
    website_url: Optional[str] = None,
    careers_url: Optional[str] = None,
) -> int:
    """Add a company to the watchlist and return its id."""
    added_at = datetime.now().isoformat()
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO watchlist (company_name, notes, added_at, sector, website_url, careers_url) VALUES (?, ?, ?, ?, ?, ?)",
            (company_name, notes, added_at, sector, website_url, careers_url),
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


def update_company_details(
    db_path: str,
    company_id: int,
    sector: Optional[str] = None,
    website_url: Optional[str] = None,
    careers_url: Optional[str] = None,
) -> None:
    """Update sector, website_url, and careers_url for a watchlist company.

    Only updates fields that are explicitly passed as non-None values.
    """
    updates = {}
    if sector is not None:
        updates["sector"] = sector
    if website_url is not None:
        updates["website_url"] = website_url
    if careers_url is not None:
        updates["careers_url"] = careers_url
    if not updates:
        return
    set_clause = ", ".join(f"{col} = ?" for col in updates)
    values = list(updates.values()) + [company_id]
    with _connect(db_path) as conn:
        conn.execute(f"UPDATE watchlist SET {set_clause} WHERE id = ?", values)


def list_companies_by_sector(db_path: str) -> dict[str, list[WatchlistCompany]]:
    """Return all watchlist companies grouped by sector.

    Companies with no sector are grouped under the key "Uncategorised".
    Sectors are sorted alphabetically; "Uncategorised" is always last.
    Companies within each sector are sorted alphabetically by company_name.
    """
    companies = list_companies(db_path)
    grouped: dict[str, list[WatchlistCompany]] = {}
    for company in companies:
        key = company.sector or "Uncategorised"
        grouped.setdefault(key, []).append(company)
    for key in grouped:
        grouped[key].sort(key=lambda c: c.company_name.lower())
    sorted_keys = sorted(k for k in grouped if k != "Uncategorised")
    if "Uncategorised" in grouped:
        sorted_keys.append("Uncategorised")
    return {k: grouped[k] for k in sorted_keys}


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
