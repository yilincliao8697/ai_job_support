import tempfile
import os
import pytest
from core.tracker import init_db
from core.watchlist import add_company, list_companies, remove_company, update_company_notes


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    yield path
    os.unlink(path)


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
