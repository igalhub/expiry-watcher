from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509

from checker.severity import compute_severity


def check_cert_file(path: str) -> dict:
    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        cert = x509.load_pem_x509_certificate(Path(path).read_bytes())
        expiry = cert.not_valid_after_utc
        days_remaining = (expiry - datetime.now(timezone.utc)).days
        return {
            "path": path,
            "days_remaining": days_remaining,
            "severity": compute_severity(days_remaining),
            "checked_at": checked_at,
            "error": None,
        }
    except Exception as e:
        return {
            "path": path,
            "days_remaining": None,
            "severity": None,
            "checked_at": checked_at,
            "error": str(e),
        }
