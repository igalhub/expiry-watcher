"""
Entry point for all expiry checks. Reads config/targets.yaml for TLS
endpoints and local cert paths, reads config/vault.yaml (if present) for
Vault credentials, runs all enabled checkers, and writes normalised results
to SQLite. Exits 0 in all cases — checker errors are written to the db
rather than raised as process failures.
"""
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from checker.db import init_db, write_results
from checker.local_cert_checker import check_cert_file
from checker.tls_checker import check_tls
from checker.vault_checker import check_vault_approle, check_vault_health, check_vault_token

_DEFAULT_CONFIG = "config/targets.yaml"
_DEFAULT_DB = os.environ.get("EXPIRY_WATCHER_DB", "results.db")
_VAULT_CREDS_PATH = "config/vault.yaml"


def _load_yaml(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text()) or {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_tls_checks(endpoints: list[dict]) -> list[dict]:
    results = []
    for ep in endpoints:
        host = ep.get("host", "")
        r = check_tls(host, port=ep.get("port", 443))
        results.append({
            "name": host, "type": "tls",
            "days_remaining": r["days_remaining"],
            "severity":       r["severity"],
            "checked_at":     r["checked_at"],
            "error":          r["error"],
        })
    return results


def _run_local_cert_checks(certs: list[dict]) -> list[dict]:
    results = []
    for cert in certs:
        path = cert.get("path", "")
        r = check_cert_file(path)
        results.append({
            "name": path, "type": "local-cert",
            "days_remaining": r["days_remaining"],
            "severity":       r["severity"],
            "checked_at":     r["checked_at"],
            "error":          r["error"],
        })
    return results


def _run_vault_checks(vault_url: str, creds: dict) -> list[dict]:
    results = []

    health = check_vault_health(vault_url)
    if not health["reachable"] or health.get("sealed"):
        msg = health.get("error", "Vault is not reachable or is sealed")
        print(f"WARNING: skipping Vault checks — {msg}", file=sys.stderr)
        results.append({
            "name": "vault", "type": "vault-health",
            "days_remaining": None, "severity": None,
            "checked_at": _now(), "error": msg,
        })
        return results

    token = creds.get("token", "")
    if token and token != "REPLACE_ME":
        results.append(check_vault_token(vault_url, token, name="vault-token"))

    role_id = creds.get("role_id", "")
    secret_id = creds.get("secret_id", "")
    if role_id and secret_id and "REPLACE_ME" not in (role_id, secret_id):
        results.append(
            check_vault_approle(vault_url, role_id, secret_id, name="vault-approle")
        )

    return results


def main(config_path: str, db_path: str) -> None:
    cfg = _load_yaml(config_path)
    if not cfg:
        print(f"ERROR: config not found or empty: {config_path}", file=sys.stderr)
        sys.exit(1)

    settings = cfg.get("settings", {})
    db = db_path or settings.get("db_path", "results.db")

    init_db(db)
    all_results: list[dict] = []

    all_results.extend(_run_tls_checks(cfg.get("tls_endpoints", [])))
    all_results.extend(_run_local_cert_checks(cfg.get("local_certs", [])))

    vault_section = cfg.get("vault", {})
    if vault_section:
        vault_url = vault_section.get("url", "http://localhost:8200")
        # Credentials come from vault.yaml (gitignored); fall back to targets.yaml
        # only if vault.yaml doesn't exist (useful for environments without secrets).
        vault_creds_file = _load_yaml(_VAULT_CREDS_PATH).get("vault", {})
        creds = vault_creds_file if vault_creds_file else vault_section
        all_results.extend(_run_vault_checks(vault_url, creds))

    write_results(db, all_results)
    print(f"Wrote {len(all_results)} result(s) to {db}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run all expiry checks")
    parser.add_argument("--config", default=_DEFAULT_CONFIG)
    parser.add_argument("--db",     default=_DEFAULT_DB)
    args = parser.parse_args()
    main(args.config, args.db)
