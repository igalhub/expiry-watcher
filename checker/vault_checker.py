import requests
import hvac
from datetime import datetime, timezone

from checker.severity import compute_severity


def check_vault_health(vault_url: str) -> dict:
    try:
        resp = requests.get(f"{vault_url}/v1/sys/health", timeout=5)
        if resp.status_code == 503:
            return {"reachable": True, "sealed": True, "error": "Vault is sealed"}
        return {"reachable": True, "sealed": False}
    except requests.exceptions.RequestException as e:
        return {"reachable": False, "sealed": None, "error": str(e)}


def check_vault_token(vault_url: str, token: str, name: str = "vault-token") -> dict:
    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        client = hvac.Client(url=vault_url, token=token)
        data = client.auth.token.lookup_self()["data"]
        ttl_seconds = data.get("ttl", 0)
        # ttl == 0 means the token never expires (e.g. root token).
        if ttl_seconds == 0:
            return {
                "name": name, "type": "vault-token",
                "days_remaining": None, "severity": "healthy",
                "checked_at": checked_at, "error": None,
            }
        days_remaining = round(ttl_seconds / 86400, 2)
        return {
            "name": name, "type": "vault-token",
            "days_remaining": days_remaining,
            "severity": compute_severity(int(days_remaining)),
            "checked_at": checked_at, "error": None,
        }
    except Exception as e:
        return {
            "name": name, "type": "vault-token",
            "days_remaining": None, "severity": None,
            "checked_at": checked_at, "error": str(e),
        }


def check_vault_approle(vault_url: str, role_id: str, secret_id: str, name: str = "vault-approle") -> dict:
    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        client = hvac.Client(url=vault_url)
        resp = client.auth.approle.login(role_id=role_id, secret_id=secret_id)
        ttl_seconds = resp["auth"]["lease_duration"]
        # ttl == 0 means the resulting token never expires.
        if ttl_seconds == 0:
            return {
                "name": name, "type": "vault-approle",
                "days_remaining": None, "severity": "healthy",
                "checked_at": checked_at, "error": None,
            }
        days_remaining = round(ttl_seconds / 86400, 2)
        return {
            "name": name, "type": "vault-approle",
            "days_remaining": days_remaining,
            "severity": compute_severity(int(days_remaining)),
            "checked_at": checked_at, "error": None,
        }
    except Exception as e:
        return {
            "name": name, "type": "vault-approle",
            "days_remaining": None, "severity": None,
            "checked_at": checked_at, "error": str(e),
        }


def check_vault_secret_id(
    vault_url: str, role_name: str, secret_id: str, lookup_token: str, name: str = "vault-secret-id"
) -> dict:
    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        client = hvac.Client(url=vault_url, token=lookup_token)
        data = client.auth.approle.read_secret_id(role_name, secret_id)["data"]
        ttl_seconds = data.get("secret_id_ttl", 0)
        # ttl == 0 means the secret_id never expires.
        if ttl_seconds == 0:
            return {
                "name": name, "type": "vault-secret-id",
                "days_remaining": None, "severity": "healthy",
                "checked_at": checked_at, "error": None,
            }
        days_remaining = round(ttl_seconds / 86400, 2)
        return {
            "name": name, "type": "vault-secret-id",
            "days_remaining": days_remaining,
            "severity": compute_severity(int(days_remaining)),
            "checked_at": checked_at, "error": None,
        }
    except Exception as e:
        return {
            "name": name, "type": "vault-secret-id",
            "days_remaining": None, "severity": None,
            "checked_at": checked_at, "error": str(e),
        }
