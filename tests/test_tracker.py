import tempfile
import os
import pytest
from core.tracker import (
    init_db, add_application, get_application, list_applications,
    update_status, update_application, delete_application,
    get_application_counts_by_date, ApplicationIn, ApplicationUpdate,
)


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    yield path
    os.unlink(path)


def sample_app(**overrides) -> ApplicationIn:
    defaults = dict(
        company="Acme Corp",
        role_title="ML Engineer",
        date_applied="2026-03-01",
        status="applied",
    )
    defaults.update(overrides)
    return ApplicationIn(**defaults)


def test_init_db_creates_tables(db_path):
    # Tables exist — adding an application should not raise
    add_application(db_path, sample_app())


def test_add_application_returns_id(db_path):
    app_id = add_application(db_path, sample_app())
    assert isinstance(app_id, int)
    assert app_id > 0


def test_get_application_retrieves_record(db_path):
    app_id = add_application(db_path, sample_app(company="Cohere"))
    app = get_application(db_path, app_id)
    assert app is not None
    assert app.company == "Cohere"
    assert app.id == app_id


def test_get_application_returns_none_for_missing(db_path):
    assert get_application(db_path, 9999) is None


def test_list_applications_active_only_excludes_rejected(db_path):
    add_application(db_path, sample_app(status="applied"))
    add_application(db_path, sample_app(status="rejected"))
    add_application(db_path, sample_app(status="ghosted"))
    add_application(db_path, sample_app(status="interview"))

    active = list_applications(db_path, active_only=True)
    statuses = {a.status for a in active}
    assert "rejected" not in statuses
    assert "ghosted" not in statuses
    assert len(active) == 2


def test_list_applications_all_includes_all_statuses(db_path):
    add_application(db_path, sample_app(status="applied"))
    add_application(db_path, sample_app(status="rejected"))
    add_application(db_path, sample_app(status="ghosted"))

    all_apps = list_applications(db_path, active_only=False)
    assert len(all_apps) == 3


def test_update_status(db_path):
    app_id = add_application(db_path, sample_app(status="applied"))
    update_status(db_path, app_id, "interview")
    app = get_application(db_path, app_id)
    assert app.status == "interview"


def test_update_application_partial(db_path):
    app_id = add_application(db_path, sample_app(company="Old Name"))
    update_application(db_path, app_id, ApplicationUpdate(company="New Name"))
    app = get_application(db_path, app_id)
    assert app.company == "New Name"
    assert app.role_title == "ML Engineer"  # unchanged


def test_delete_application(db_path):
    app_id = add_application(db_path, sample_app())
    delete_application(db_path, app_id)
    assert get_application(db_path, app_id) is None


def test_get_application_counts_by_date(db_path):
    add_application(db_path, sample_app(date_applied="2026-01-01"))
    add_application(db_path, sample_app(date_applied="2026-01-01"))
    add_application(db_path, sample_app(date_applied="2026-01-03"))

    counts = get_application_counts_by_date(db_path)
    assert len(counts) == 2  # two distinct dates
    assert counts[0]["date"] == "2026-01-01"
    assert counts[0]["cumulative_count"] == 2
    assert counts[1]["date"] == "2026-01-03"
    assert counts[1]["cumulative_count"] == 3
