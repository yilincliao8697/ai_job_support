import os
import tempfile
import pytest
from core.tracker import init_db
from core.resume_store import (
    init_resumes_table,
    migrate_resumes,
    record_resume,
    list_resumes,
    get_resume,
    get_revision_chain,
    link_application,
    delete_resume_record,
)


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    init_resumes_table(path)
    migrate_resumes(path)
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


# ---------------------------------------------------------------------------
# migrate_resumes
# ---------------------------------------------------------------------------

def test_migrate_resumes_adds_columns(db_path):
    migrate_resumes(db_path)
    rid = record_resume(db_path, "stripe.pdf", "Stripe", "Engineer", job_description="We are hiring.", parent_id=None, feedback_summary="Shorter summary.")
    result = get_resume(db_path, rid)
    assert result.job_description == "We are hiring."
    assert result.feedback_summary == "Shorter summary."


def test_migrate_resumes_is_idempotent(db_path):
    migrate_resumes(db_path)
    migrate_resumes(db_path)  # should not raise


# ---------------------------------------------------------------------------
# record_resume with new fields
# ---------------------------------------------------------------------------

def test_record_resume_stores_job_description_and_parent_id(db_path):
    migrate_resumes(db_path)
    v1 = record_resume(db_path, "v1.pdf", "Stripe", "Engineer", job_description="Some JD text.")
    v2 = record_resume(db_path, "v2.pdf", "Stripe", "Engineer", job_description="Some JD text.", parent_id=v1, feedback_summary="Shorter bullets.")
    result = get_resume(db_path, v2)
    assert result.job_description == "Some JD text."
    assert result.parent_id == v1
    assert result.feedback_summary == "Shorter bullets."


# ---------------------------------------------------------------------------
# get_revision_chain
# ---------------------------------------------------------------------------

def test_get_revision_chain_single_record(db_path):
    migrate_resumes(db_path)
    rid = record_resume(db_path, "v1.pdf", "Stripe", "Engineer")
    chain = get_revision_chain(db_path, rid)
    assert len(chain) == 1
    assert chain[0].id == rid


def test_get_revision_chain_two_generations_oldest_first(db_path):
    migrate_resumes(db_path)
    v1 = record_resume(db_path, "v1.pdf", "Stripe", "Engineer")
    v2 = record_resume(db_path, "v2.pdf", "Stripe", "Engineer", parent_id=v1)
    chain = get_revision_chain(db_path, v2)
    assert len(chain) == 2
    assert chain[0].id == v1
    assert chain[1].id == v2


def test_get_revision_chain_three_generations_oldest_first(db_path):
    migrate_resumes(db_path)
    v1 = record_resume(db_path, "v1.pdf", "Stripe", "Engineer")
    v2 = record_resume(db_path, "v2.pdf", "Stripe", "Engineer", parent_id=v1)
    v3 = record_resume(db_path, "v3.pdf", "Stripe", "Engineer", parent_id=v2)
    chain = get_revision_chain(db_path, v3)
    assert len(chain) == 3
    assert chain[0].id == v1
    assert chain[1].id == v2
    assert chain[2].id == v3
