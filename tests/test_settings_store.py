import os
import tempfile
import pytest
from core.settings_store import init_settings_table, get_setting, set_setting, delete_setting


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_settings_table(path)
    yield path
    os.unlink(path)


def test_init_is_idempotent(db_path):
    init_settings_table(db_path)  # second call must not raise


def test_get_missing_key_returns_none(db_path):
    assert get_setting(db_path, "anthropic_api_key") is None


def test_set_and_get(db_path):
    set_setting(db_path, "anthropic_api_key", "sk-test-123")
    assert get_setting(db_path, "anthropic_api_key") == "sk-test-123"


def test_set_overwrites(db_path):
    set_setting(db_path, "anthropic_api_key", "old")
    set_setting(db_path, "anthropic_api_key", "new")
    assert get_setting(db_path, "anthropic_api_key") == "new"


def test_delete_removes_key(db_path):
    set_setting(db_path, "anthropic_api_key", "sk-test-123")
    delete_setting(db_path, "anthropic_api_key")
    assert get_setting(db_path, "anthropic_api_key") is None


def test_delete_missing_key_does_not_raise(db_path):
    delete_setting(db_path, "nonexistent")  # must not raise


def test_multiple_keys_are_independent(db_path):
    set_setting(db_path, "key_a", "value_a")
    set_setting(db_path, "key_b", "value_b")
    assert get_setting(db_path, "key_a") == "value_a"
    assert get_setting(db_path, "key_b") == "value_b"
    delete_setting(db_path, "key_a")
    assert get_setting(db_path, "key_a") is None
    assert get_setting(db_path, "key_b") == "value_b"
