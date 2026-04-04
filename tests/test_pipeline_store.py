import pytest
from core.pipeline_store import (
    init_pipelines_table, create_pipeline, get_pipeline,
    update_pipeline, list_active_pipelines, complete_pipeline,
    delete_pipeline,
)


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_pipelines_table(db_path)
    return db_path


# ---------------------------------------------------------------------------
# create_pipeline
# ---------------------------------------------------------------------------

def test_create_pipeline_returns_int(db):
    pipeline_id = create_pipeline(db)
    assert isinstance(pipeline_id, int)
    assert pipeline_id > 0


def test_create_pipeline_defaults_to_stage_1(db):
    pipeline_id = create_pipeline(db)
    pipeline = get_pipeline(db, pipeline_id)
    assert pipeline["stage"] == 1


def test_create_pipeline_defaults_empty_strings(db):
    pipeline_id = create_pipeline(db)
    pipeline = get_pipeline(db, pipeline_id)
    assert pipeline["job_title"] == ""
    assert pipeline["company"] == ""
    assert pipeline["jd_text"] == ""


def test_create_pipeline_not_completed(db):
    pipeline_id = create_pipeline(db)
    pipeline = get_pipeline(db, pipeline_id)
    assert pipeline["completed_at"] is None


# ---------------------------------------------------------------------------
# get_pipeline
# ---------------------------------------------------------------------------

def test_get_pipeline_returns_none_for_missing(db):
    assert get_pipeline(db, 9999) is None


def test_get_pipeline_returns_dict(db):
    pipeline_id = create_pipeline(db)
    result = get_pipeline(db, pipeline_id)
    assert isinstance(result, dict)
    assert result["id"] == pipeline_id


# ---------------------------------------------------------------------------
# update_pipeline
# ---------------------------------------------------------------------------

def test_update_pipeline_single_field(db):
    pipeline_id = create_pipeline(db)
    update_pipeline(db, pipeline_id, stage=2)
    assert get_pipeline(db, pipeline_id)["stage"] == 2


def test_update_pipeline_multiple_fields(db):
    pipeline_id = create_pipeline(db)
    update_pipeline(db, pipeline_id, job_title="ML Engineer", company="Acme Corp", stage=2)
    pipeline = get_pipeline(db, pipeline_id)
    assert pipeline["job_title"] == "ML Engineer"
    assert pipeline["company"] == "Acme Corp"
    assert pipeline["stage"] == 2


def test_update_pipeline_no_fields_is_safe(db):
    pipeline_id = create_pipeline(db)
    update_pipeline(db, pipeline_id)  # should not raise


def test_update_pipeline_resume_id(db):
    pipeline_id = create_pipeline(db)
    update_pipeline(db, pipeline_id, resume_id=42)
    assert get_pipeline(db, pipeline_id)["resume_id"] == 42


def test_update_pipeline_cover_letter_id(db):
    pipeline_id = create_pipeline(db)
    update_pipeline(db, pipeline_id, cover_letter_id=7)
    assert get_pipeline(db, pipeline_id)["cover_letter_id"] == 7


def test_update_pipeline_skipped_cover_letter(db):
    pipeline_id = create_pipeline(db)
    update_pipeline(db, pipeline_id, skipped_cover_letter=1, stage=5)
    pipeline = get_pipeline(db, pipeline_id)
    assert pipeline["skipped_cover_letter"] == 1
    assert pipeline["stage"] == 5


# ---------------------------------------------------------------------------
# list_active_pipelines
# ---------------------------------------------------------------------------

def test_list_active_pipelines_empty(db):
    assert list_active_pipelines(db) == []


def test_list_active_pipelines_returns_incomplete_only(db):
    id1 = create_pipeline(db)
    id2 = create_pipeline(db)
    complete_pipeline(db, id1, application_id=99)
    active = list_active_pipelines(db)
    assert len(active) == 1
    assert active[0]["id"] == id2


def test_list_active_pipelines_newest_first(db):
    id1 = create_pipeline(db)
    id2 = create_pipeline(db)
    active = list_active_pipelines(db)
    assert active[0]["id"] == id2
    assert active[1]["id"] == id1


# ---------------------------------------------------------------------------
# complete_pipeline
# ---------------------------------------------------------------------------

def test_complete_pipeline_sets_completed_at(db):
    pipeline_id = create_pipeline(db)
    complete_pipeline(db, pipeline_id, application_id=5)
    pipeline = get_pipeline(db, pipeline_id)
    assert pipeline["completed_at"] is not None


def test_complete_pipeline_sets_application_id(db):
    pipeline_id = create_pipeline(db)
    complete_pipeline(db, pipeline_id, application_id=5)
    assert get_pipeline(db, pipeline_id)["application_id"] == 5


def test_complete_pipeline_excluded_from_active_list(db):
    pipeline_id = create_pipeline(db)
    complete_pipeline(db, pipeline_id, application_id=5)
    assert list_active_pipelines(db) == []


# ---------------------------------------------------------------------------
# delete_pipeline
# ---------------------------------------------------------------------------

def test_delete_pipeline(db):
    pipeline_id = create_pipeline(db)
    delete_pipeline(db, pipeline_id)
    assert get_pipeline(db, pipeline_id) is None


def test_delete_nonexistent_pipeline_is_safe(db):
    delete_pipeline(db, 9999)  # should not raise


# ---------------------------------------------------------------------------
# init idempotency
# ---------------------------------------------------------------------------

def test_init_pipelines_table_is_idempotent(db):
    init_pipelines_table(db)  # second call — should not raise
