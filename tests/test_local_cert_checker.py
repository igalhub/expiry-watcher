from datetime import datetime, timezone, timedelta

import pytest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from checker.local_cert_checker import check_cert_file


def _write_cert(path, cn, not_before, not_after):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .sign(key, hashes.SHA256())
    )
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


@pytest.fixture(scope="session")
def critical_cert_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("fixtures") / "critical_cert.pem"
    now = datetime.now(timezone.utc)
    _write_cert(
        path,
        cn="critical-test-cert.invalid",
        not_before=now - timedelta(days=1),
        not_after=now + timedelta(days=5),
    )
    return str(path)


def test_valid_cert_is_healthy():
    result = check_cert_file("tests/fixtures/valid_cert.pem")
    assert result["error"] is None
    assert result["days_remaining"] is not None
    assert result["days_remaining"] > 30
    assert result["severity"] == "healthy"


def test_expired_cert_is_expired():
    result = check_cert_file("tests/fixtures/expired_cert.pem")
    assert result["error"] is None, f"Unexpected error: {result['error']}"
    assert result["days_remaining"] is not None
    assert result["days_remaining"] <= 0
    assert result["severity"] == "expired"


def test_critical_cert_is_critical(critical_cert_path):
    result = check_cert_file(critical_cert_path)
    assert result["error"] is None
    assert result["days_remaining"] is not None
    assert 1 <= result["days_remaining"] <= 7
    assert result["severity"] == "critical"


def test_missing_file_sets_error():
    result = check_cert_file("/nonexistent/path/cert.pem")
    assert result["error"] is not None
    assert result["days_remaining"] is None
    assert result["severity"] is None


def test_result_always_contains_path_and_checked_at():
    result = check_cert_file("/nonexistent/path/cert.pem")
    assert result["path"] == "/nonexistent/path/cert.pem"
    assert result["checked_at"] is not None
