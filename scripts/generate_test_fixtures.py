"""
Generate static test fixture certificates for tests/fixtures/.

These are self-signed certs with obviously fake CNs — not real certs.
Run from the project root: python scripts/generate_test_fixtures.py
"""
from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def _make_cert(cn: str, not_before: datetime, not_after: datetime) -> bytes:
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
    return cert.public_bytes(serialization.Encoding.PEM)


if __name__ == "__main__":
    out = Path("tests/fixtures")
    out.mkdir(parents=True, exist_ok=True)

    (out / "valid_cert.pem").write_bytes(_make_cert(
        cn="valid-test-cert.invalid",
        not_before=datetime(2024, 1, 1, tzinfo=timezone.utc),
        not_after=datetime(2036, 1, 1, tzinfo=timezone.utc),
    ))
    print("wrote tests/fixtures/valid_cert.pem  (expires 2036-01-01)")

    (out / "expired_cert.pem").write_bytes(_make_cert(
        cn="expired-test-cert.invalid",
        not_before=datetime(2019, 1, 1, tzinfo=timezone.utc),
        not_after=datetime(2020, 1, 1, tzinfo=timezone.utc),
    ))
    print("wrote tests/fixtures/expired_cert.pem  (expired 2020-01-01)")
