import os
import tempfile
import pytest
from core.tracker import init_db
from core.resume_store import (
    init_resumes_table,
    record_resume,
    list_resumes,
    get_resume,
    link_application,
    delete_resume_record,
)


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    init_resumes_table(path)
    yield path
    os.unlink(path)


def test_init_resumes_table_creates_table(db_path):
    # Should not raise; record_resume exercises the table
    resume_id = record_resume(db_path, "stripe_2026-03-23.pdf", "Stripe", "ML Engineer")
    assert isinstance(resume_id, int)


def test_init_resumes_table_is_idempotent(db_path):
    init_resumes_table(db_path)  # second call should not raise


def test_record_resume_returns_valid_id(db_path):
    resume_id = record_resume(db_path, "cohere_2026-03-23.pdf", "Cohere", "AI Engineer")
    assert isinstance(resume_id, int)
    assert resume_id > 0


def test_list_resumes_returns_inserted_records_newest_first(db_path):
    record_resume(db_path, "first.pdf", "Alpha", "Engineer")
    record_resume(db_path, "second.pdf", "Beta", "Engineer")
    resumes = list_resumes(db_path)
    assert len(resumes) == 2
    # Newest first — second inserted should appear first
    assert resumes[0].filename == "second.pdf"
    assert resumes[1].filename == "first.pdf"


def test_get_resume_returns_correct_record(db_path):
    resume_id = record_resume(db_path, "stripe_2026.pdf", "Stripe", "ML Engineer")
    result = get_resume(db_path, resume_id)
    assert result is not None
    assert result.id == resume_id
    assert result.filename == "stripe_2026.pdf"
    assert result.company == "Stripe"
    assert result.role == "ML Engineer"


def test_get_resume_returns_none_for_missing(db_path):
    result = get_resume(db_path, 9999)
    assert result is None


def test_link_application_sets_application_id(db_path):
    resume_id = record_resume(db_path, "stripe.pdf", "Stripe", "Engineer")
    link_application(db_path, resume_id, 42)
    result = get_resume(db_path, resume_id)
    assert result.application_id == 42


def test_delete_resume_record_removes_record(db_path):
    resume_id = record_resume(db_path, "stripe.pdf", "Stripe", "Engineer")
    delete_resume_record(db_path, resume_id)
    assert get_resume(db_path, resume_id) is None


def test_delete_resume_record_does_not_raise_for_missing(db_path):
    delete_resume_record(db_path, 9999)  # should not raise
