from contextlib import ExitStack
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from dashboard.main import app

client = TestClient(app)

_SAMPLE = [
    {"name": "google.com",         "type": "tls",        "days_remaining": 55,    "severity": "healthy",  "checked_at": "2026-06-22T00:00:00+00:00", "error": None},
    {"name": "expired.badssl.com", "type": "tls",        "days_remaining": -4089, "severity": "expired",  "checked_at": "2026-06-22T00:00:00+00:00", "error": None},
    {"name": "/cert.pem",          "type": "local-cert", "days_remaining": 5,     "severity": "critical", "checked_at": "2026-06-22T00:00:00+00:00", "error": None},
]

_RECENT = datetime.now(timezone.utc) - timedelta(minutes=5)
_STALE  = datetime.now(timezone.utc) - timedelta(hours=13)


def _patch_db(last_checked=_RECENT, items=_SAMPLE):
    stack = ExitStack()
    stack.enter_context(patch("dashboard.main.read_results",    return_value=items))
    stack.enter_context(patch("dashboard.main.get_last_checked", return_value=last_checked))
    stack.enter_context(patch("dashboard.main._db_exists",      return_value=True))
    return stack


# --- GET /status ---

def test_status_200_with_correct_keys():
    with _patch_db():
        r = client.get("/status")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "last_checked" in data
    assert "stale" in data


def test_status_item_count():
    with _patch_db():
        r = client.get("/status")
    assert len(r.json()["items"]) == len(_SAMPLE)


def test_status_not_stale_when_recent():
    with _patch_db(last_checked=_RECENT):
        r = client.get("/status")
    assert r.json()["stale"] is False


def test_status_stale_when_old():
    with _patch_db(last_checked=_STALE):
        r = client.get("/status")
    assert r.json()["stale"] is True


def test_status_stale_when_no_db():
    with patch("dashboard.main._db_exists", return_value=False):
        r = client.get("/status")
    assert r.status_code == 200
    assert r.json()["stale"] is True
    assert r.json()["items"] == []


# --- GET / ---

def test_index_200_html():
    with _patch_db():
        r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_index_contains_severity_classes():
    with _patch_db():
        r = client.get("/")
    assert "ti-circle-check" in r.text    # healthy icon
    assert "ti-alert-circle" in r.text    # expired icon
    assert "ti-alert-triangle" in r.text  # critical/warning icon


def test_index_shows_stale_banner_when_stale():
    with _patch_db(last_checked=_STALE):
        r = client.get("/")
    assert "Data is stale" in r.text


def test_index_no_stale_banner_when_fresh():
    with _patch_db(last_checked=_RECENT):
        r = client.get("/")
    assert "Data is stale" not in r.text


# --- read-only enforcement ---

def _write_guard(*a, **kw):
    raise AssertionError("write_results was called from the dashboard")


def test_write_not_called_from_status():
    with patch("checker.db.write_results", _write_guard), _patch_db():
        r = client.get("/status")
    assert r.status_code == 200


def test_write_not_called_from_index():
    with patch("checker.db.write_results", _write_guard), _patch_db():
        r = client.get("/")
    assert r.status_code == 200
