import tempfile
import os
import pytest
from core.tracker import init_db
from core.watchlist import (
    add_company,
    list_companies,
    list_companies_by_sector,
    migrate_watchlist,
    remove_company,
    update_company_details,
    update_company_notes,
)


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    yield path
    os.unlink(path)


# ---------------------------------------------------------------------------
# Existing tests
# ---------------------------------------------------------------------------

def test_add_company_returns_id(db_path):
    company_id = add_company(db_path, "Cohere")
    assert isinstance(company_id, int)
    assert company_id > 0


def test_list_companies_returns_inserted(db_path):
    add_company(db_path, "Cohere")
    add_company(db_path, "Mistral")
    companies = list_companies(db_path)
    names = [c.company_name for c in companies]
    assert "Cohere" in names
    assert "Mistral" in names


def test_remove_company(db_path):
    company_id = add_company(db_path, "Cohere")
    remove_company(db_path, company_id)
    companies = list_companies(db_path)
    assert all(c.id != company_id for c in companies)


def test_update_company_notes(db_path):
    company_id = add_company(db_path, "Cohere")
    update_company_notes(db_path, company_id, "Series C, strong LLM focus")
    companies = list_companies(db_path)
    cohere = next(c for c in companies if c.id == company_id)
    assert cohere.notes == "Series C, strong LLM focus"


# ---------------------------------------------------------------------------
# Migration tests
# ---------------------------------------------------------------------------

def test_migrate_watchlist_adds_new_columns(db_path):
    migrate_watchlist(db_path)
    companies = list_companies(db_path)
    # If migration ran, WatchlistCompany fields exist — adding a company and
    # reading it back exercises all columns without error.
    cid = add_company(db_path, "Stripe", sector="Fintech", website_url="https://stripe.com")
    result = next(c for c in list_companies(db_path) if c.id == cid)
    assert result.sector == "Fintech"
    assert result.website_url == "https://stripe.com"
    assert result.careers_url is None


def test_migrate_watchlist_is_idempotent(db_path):
    migrate_watchlist(db_path)
    migrate_watchlist(db_path)  # should not raise


# ---------------------------------------------------------------------------
# add_company with new fields
# ---------------------------------------------------------------------------

def test_add_company_with_sector_and_urls(db_path):
    cid = add_company(
        db_path,
        "Stripe",
        sector="Fintech",
        website_url="https://stripe.com",
        careers_url="https://stripe.com/jobs",
    )
    result = next(c for c in list_companies(db_path) if c.id == cid)
    assert result.sector == "Fintech"
    assert result.website_url == "https://stripe.com"
    assert result.careers_url == "https://stripe.com/jobs"


def test_add_company_without_sector_urls(db_path):
    cid = add_company(db_path, "Cohere")
    result = next(c for c in list_companies(db_path) if c.id == cid)
    assert result.sector is None
    assert result.website_url is None
    assert result.careers_url is None


# ---------------------------------------------------------------------------
# update_company_details
# ---------------------------------------------------------------------------

def test_update_company_details_updates_only_passed_fields(db_path):
    cid = add_company(db_path, "Stripe", sector="Fintech", website_url="https://stripe.com")
    # Update only careers_url — sector and website_url should be unchanged.
    update_company_details(db_path, cid, careers_url="https://stripe.com/jobs")
    result = next(c for c in list_companies(db_path) if c.id == cid)
    assert result.sector == "Fintech"
    assert result.website_url == "https://stripe.com"
    assert result.careers_url == "https://stripe.com/jobs"


def test_update_company_details_all_fields(db_path):
    cid = add_company(db_path, "Cohere")
    update_company_details(
        db_path, cid,
        sector="LLM Tooling",
        website_url="https://cohere.com",
        careers_url="https://cohere.com/careers",
    )
    result = next(c for c in list_companies(db_path) if c.id == cid)
    assert result.sector == "LLM Tooling"
    assert result.website_url == "https://cohere.com"
    assert result.careers_url == "https://cohere.com/careers"


def test_update_company_details_no_args_is_noop(db_path):
    cid = add_company(db_path, "Cohere", sector="LLM Tooling")
    update_company_details(db_path, cid)  # no-op
    result = next(c for c in list_companies(db_path) if c.id == cid)
    assert result.sector == "LLM Tooling"


# ---------------------------------------------------------------------------
# list_companies_by_sector
# ---------------------------------------------------------------------------

def test_list_companies_by_sector_groups_correctly(db_path):
    add_company(db_path, "Stripe", sector="Fintech")
    add_company(db_path, "Plaid", sector="Fintech")
    add_company(db_path, "Cohere", sector="LLM Tooling")
    grouped = list_companies_by_sector(db_path)
    assert "Fintech" in grouped
    assert "LLM Tooling" in grouped
    fintech_names = [c.company_name for c in grouped["Fintech"]]
    assert "Stripe" in fintech_names
    assert "Plaid" in fintech_names


def test_list_companies_by_sector_uncategorised_key(db_path):
    add_company(db_path, "Mystery Co")  # no sector
    grouped = list_companies_by_sector(db_path)
    assert "Uncategorised" in grouped
    names = [c.company_name for c in grouped["Uncategorised"]]
    assert "Mystery Co" in names


def test_list_companies_by_sector_uncategorised_is_last(db_path):
    add_company(db_path, "Mystery Co")
    add_company(db_path, "Stripe", sector="Fintech")
    grouped = list_companies_by_sector(db_path)
    keys = list(grouped.keys())
    assert keys[-1] == "Uncategorised"


def test_list_companies_by_sector_sorted_alphabetically_within_sector(db_path):
    add_company(db_path, "Zebra Inc", sector="Fintech")
    add_company(db_path, "Apple Pay", sector="Fintech")
    grouped = list_companies_by_sector(db_path)
    names = [c.company_name for c in grouped["Fintech"]]
    assert names == sorted(names, key=str.lower)
