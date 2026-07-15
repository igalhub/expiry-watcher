from datetime import datetime, timezone

import pytest

from checker.db import get_last_checked, init_db, read_results, write_results


@pytest.fixture()
def db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


def test_init_creates_schema(db):
    # read_results on a fresh db returns an empty list, not an error
    assert read_results(db) == []


def test_write_and_read_single_result(db):
    results = [{
        "name": "example.com", "type": "tls",
        "days_remaining": 45.0, "severity": "healthy",
        "checked_at": "2026-06-22T00:00:00+00:00", "error": None,
    }]
    write_results(db, results)
    rows = read_results(db)
    assert len(rows) == 1
    assert rows[0]["name"] == "example.com"
    assert rows[0]["type"] == "tls"
    assert rows[0]["days_remaining"] == 45.0
    assert rows[0]["severity"] == "healthy"
    assert rows[0]["error"] is None


def test_write_and_read_fractional_days_remaining(db):
    # EW-015: a Vault-style fractional TTL must survive the round trip
    # exactly, not get truncated to int() on write.
    results = [{
        "name": "vault", "type": "vault-approle",
        "days_remaining": 6.23, "severity": "warning",
        "checked_at": "2026-06-22T00:00:00+00:00", "error": None,
    }]
    write_results(db, results)
    rows = read_results(db)
    assert rows[0]["days_remaining"] == 6.23


def test_write_and_read_whole_day_int_style(db):
    # TLS/local-cert checkers produce a plain Python int via `.days`.
    results = [{
        "name": "example.com", "type": "tls",
        "days_remaining": 45, "severity": "healthy",
        "checked_at": "2026-06-22T00:00:00+00:00", "error": None,
    }]
    write_results(db, results)
    rows = read_results(db)
    assert rows[0]["days_remaining"] == 45
    assert isinstance(rows[0]["days_remaining"], int)


def test_write_upserts_on_name_type(db):
    row = {
        "name": "example.com", "type": "tls",
        "days_remaining": 45.0, "severity": "healthy",
        "checked_at": "2026-06-22T00:00:00+00:00", "error": None,
    }
    write_results(db, [row])
    row_updated = {**row, "days_remaining": 3.0, "severity": "critical"}
    write_results(db, [row_updated])
    rows = read_results(db)
    assert len(rows) == 1
    assert rows[0]["days_remaining"] == 3.0
    assert rows[0]["severity"] == "critical"


def test_write_multiple_distinct_results(db):
    results = [
        {"name": "a.com",  "type": "tls",        "days_remaining": 60.0,  "severity": "healthy",  "checked_at": "2026-06-22T00:00:00+00:00", "error": None},
        {"name": "/c.pem", "type": "local-cert",  "days_remaining": -10.0, "severity": "expired",  "checked_at": "2026-06-22T00:00:00+00:00", "error": None},
        {"name": "vault",  "type": "vault-approle","days_remaining": 5.0,  "severity": "critical", "checked_at": "2026-06-22T00:00:00+00:00", "error": None},
    ]
    write_results(db, results)
    rows = read_results(db)
    assert len(rows) == 3


def test_write_result_with_error(db):
    results = [{
        "name": "bad.host", "type": "tls",
        "days_remaining": None, "severity": None,
        "checked_at": "2026-06-22T00:00:00+00:00", "error": "connection refused",
    }]
    write_results(db, results)
    rows = read_results(db)
    assert rows[0]["error"] == "connection refused"
    assert rows[0]["days_remaining"] is None


def test_get_last_checked_none_before_write(db):
    assert get_last_checked(db) is None


def test_get_last_checked_after_write(db):
    write_results(db, [{
        "name": "x", "type": "tls",
        "days_remaining": 10.0, "severity": "warning",
        "checked_at": "2026-06-22T00:00:00+00:00", "error": None,
    }])
    ts = get_last_checked(db)
    assert isinstance(ts, datetime)
    assert ts.tzinfo is not None


def test_get_last_checked_updates_on_second_write(db):
    row = {"name": "x", "type": "tls", "days_remaining": 10.0,
           "severity": "warning", "checked_at": "2026-06-22T00:00:00+00:00", "error": None}
    write_results(db, [row])
    first = get_last_checked(db)
    write_results(db, [row])
    second = get_last_checked(db)
    assert second >= first
