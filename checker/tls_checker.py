import socket
import ssl
from datetime import datetime, timezone

from cryptography import x509

from checker.severity import compute_severity


def check_tls(host: str, port: int = 443, timeout: int = 10) -> dict:
    checked_at = datetime.now(timezone.utc).isoformat()

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                der_bytes = ssock.getpeercert(binary_form=True)

        cert = x509.load_der_x509_certificate(der_bytes)
        expiry = cert.not_valid_after_utc
        days_remaining = (expiry - datetime.now(timezone.utc)).days

        return {
            "host": host,
            "port": port,
            "days_remaining": days_remaining,
            "severity": compute_severity(days_remaining),
            "checked_at": checked_at,
            "error": None,
        }
    except Exception as e:
        return {
            "host": host,
            "port": port,
            "days_remaining": None,
            "severity": None,
            "checked_at": checked_at,
            "error": str(e),
        }
