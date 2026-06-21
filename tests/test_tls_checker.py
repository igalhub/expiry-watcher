import socket
from unittest.mock import patch

import pytest

from checker.tls_checker import check_tls


# --- offline tests ---

def test_connection_refused_sets_error():
    with patch("socket.create_connection", side_effect=ConnectionRefusedError("refused")):
        result = check_tls("unreachable.example.com")
    assert result["error"] is not None
    assert result["days_remaining"] is None
    assert result["severity"] is None


def test_dns_failure_sets_error():
    with patch("socket.create_connection", side_effect=socket.gaierror("name or service not known")):
        result = check_tls("this-does-not-exist.invalid")
    assert result["error"] is not None
    assert result["days_remaining"] is None
    assert result["severity"] is None


def test_timeout_sets_error():
    with patch("socket.create_connection", side_effect=TimeoutError("timed out")):
        result = check_tls("timeout.example.com")
    assert result["error"] is not None
    assert result["days_remaining"] is None
    assert result["severity"] is None


def test_result_always_contains_host_port_checked_at():
    with patch("socket.create_connection", side_effect=OSError("network unreachable")):
        result = check_tls("host.example.com", port=8443)
    assert result["host"] == "host.example.com"
    assert result["port"] == 8443
    assert "checked_at" in result
    assert result["checked_at"] is not None


# --- live network tests ---

@pytest.mark.network
def test_healthy_domain():
    result = check_tls("google.com")
    assert result["error"] is None, f"Unexpected error: {result['error']}"
    assert result["days_remaining"] is not None
    assert result["days_remaining"] > 0
    assert result["severity"] == "healthy"


@pytest.mark.network
def test_expired_badssl():
    result = check_tls("expired.badssl.com")
    assert result["error"] is None, f"Unexpected error: {result['error']}"
    assert result["days_remaining"] is not None
    assert result["days_remaining"] <= 0
    assert result["severity"] == "expired"
