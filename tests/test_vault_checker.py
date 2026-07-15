from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from checker.vault_checker import (
    check_vault_approle,
    check_vault_health,
    check_vault_secret_id,
    check_vault_token,
)

VAULT_URL = "http://localhost:8200"

_SKIP_MSG = (
    "Vault is not reachable or is sealed. "
    "Start it with: docker compose -f ../vault-secrets-demo/docker-compose.yml up vault -d "
    "&& bash ../vault-secrets-demo/scripts/unseal.sh"
)


def _vault_config() -> dict:
    path = Path("config/vault.yaml")
    if not path.exists():
        pytest.skip("config/vault.yaml not found")
    return yaml.safe_load(path.read_text()).get("vault", {})


def _require_healthy_vault():
    health = check_vault_health(VAULT_URL)
    if not health["reachable"] or health.get("sealed"):
        pytest.skip(_SKIP_MSG)


# --- offline: check_vault_health ---

def test_health_unreachable():
    import requests as req_module
    with patch("requests.get", side_effect=req_module.exceptions.ConnectionError("connection refused")):
        result = check_vault_health(VAULT_URL)
    assert result["reachable"] is False
    assert result["sealed"] is None
    assert result["error"] is not None


def test_health_sealed():
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    with patch("requests.get", return_value=mock_resp):
        result = check_vault_health(VAULT_URL)
    assert result["reachable"] is True
    assert result["sealed"] is True
    assert "sealed" in result["error"].lower()


def test_health_ok():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("requests.get", return_value=mock_resp):
        result = check_vault_health(VAULT_URL)
    assert result["reachable"] is True
    assert result["sealed"] is False


# --- offline: check_vault_token ---

def test_token_healthy_ttl():
    mock_client = MagicMock()
    mock_client.auth.token.lookup_self.return_value = {"data": {"ttl": 40 * 86400}}
    with patch("hvac.Client", return_value=mock_client):
        result = check_vault_token(VAULT_URL, "fake-token", name="test-token")
    assert result["error"] is None
    assert result["days_remaining"] == 40.0
    assert result["severity"] == "healthy"


def test_token_critical_ttl():
    mock_client = MagicMock()
    mock_client.auth.token.lookup_self.return_value = {"data": {"ttl": 5 * 86400}}
    with patch("hvac.Client", return_value=mock_client):
        result = check_vault_token(VAULT_URL, "fake-token", name="test-token")
    assert result["severity"] == "critical"
    assert result["days_remaining"] == 5.0


def test_token_no_expiry():
    mock_client = MagicMock()
    mock_client.auth.token.lookup_self.return_value = {"data": {"ttl": 0}}
    with patch("hvac.Client", return_value=mock_client):
        result = check_vault_token(VAULT_URL, "fake-token")
    assert result["severity"] == "healthy"
    assert result["days_remaining"] is None
    assert result["error"] is None


def test_token_vault_error():
    mock_client = MagicMock()
    mock_client.auth.token.lookup_self.side_effect = Exception("connection refused")
    with patch("hvac.Client", return_value=mock_client):
        result = check_vault_token(VAULT_URL, "fake-token")
    assert result["error"] is not None
    assert result["days_remaining"] is None
    assert result["severity"] is None


# --- offline: check_vault_approle ---

def test_approle_healthy_ttl():
    mock_client = MagicMock()
    mock_client.auth.approle.login.return_value = {"auth": {"lease_duration": 40 * 86400}}
    with patch("hvac.Client", return_value=mock_client):
        result = check_vault_approle(VAULT_URL, "fake-role-id", "fake-secret-id")
    assert result["error"] is None
    assert result["days_remaining"] == 40.0
    assert result["severity"] == "healthy"


def test_approle_critical_ttl():
    mock_client = MagicMock()
    mock_client.auth.approle.login.return_value = {"auth": {"lease_duration": 5 * 86400}}
    with patch("hvac.Client", return_value=mock_client):
        result = check_vault_approle(VAULT_URL, "fake-role-id", "fake-secret-id")
    assert result["severity"] == "critical"
    assert result["days_remaining"] == 5.0


def test_approle_vault_error():
    mock_client = MagicMock()
    mock_client.auth.approle.login.side_effect = Exception("permission denied")
    with patch("hvac.Client", return_value=mock_client):
        result = check_vault_approle(VAULT_URL, "fake-role-id", "fake-secret-id")
    assert result["error"] is not None
    assert result["days_remaining"] is None
    assert result["severity"] is None


# --- offline: check_vault_secret_id ---

def test_secret_id_healthy_unbounded():
    mock_client = MagicMock()
    mock_client.auth.approle.read_secret_id.return_value = {"data": {"secret_id_ttl": 0}}
    with patch("hvac.Client", return_value=mock_client):
        result = check_vault_secret_id(VAULT_URL, "fake-role", "fake-secret-id", "fake-lookup-token")
    assert result["error"] is None
    assert result["days_remaining"] is None
    assert result["severity"] == "healthy"


def test_secret_id_critical_ttl():
    mock_client = MagicMock()
    mock_client.auth.approle.read_secret_id.return_value = {"data": {"secret_id_ttl": 5 * 86400}}
    with patch("hvac.Client", return_value=mock_client):
        result = check_vault_secret_id(VAULT_URL, "fake-role", "fake-secret-id", "fake-lookup-token")
    assert result["error"] is None
    assert result["days_remaining"] == 5.0
    assert result["severity"] == "critical"


def test_secret_id_warning_ttl():
    mock_client = MagicMock()
    mock_client.auth.approle.read_secret_id.return_value = {"data": {"secret_id_ttl": 20 * 86400}}
    with patch("hvac.Client", return_value=mock_client):
        result = check_vault_secret_id(VAULT_URL, "fake-role", "fake-secret-id", "fake-lookup-token")
    assert result["error"] is None
    assert result["days_remaining"] == 20.0
    assert result["severity"] == "warning"


def test_secret_id_vault_error():
    mock_client = MagicMock()
    mock_client.auth.approle.read_secret_id.side_effect = Exception("permission denied")
    with patch("hvac.Client", return_value=mock_client):
        result = check_vault_secret_id(VAULT_URL, "fake-role", "fake-secret-id", "fake-lookup-token")
    assert result["error"] is not None
    assert result["days_remaining"] is None
    assert result["severity"] is None


# --- live vault tests ---

@pytest.mark.vault
def test_live_vault_health():
    _require_healthy_vault()
    result = check_vault_health(VAULT_URL)
    assert result["reachable"] is True
    assert result["sealed"] is False


@pytest.mark.vault
def test_live_token_healthy():
    _require_healthy_vault()
    cfg = _vault_config()
    token = cfg.get("token", "")
    if not token or token == "REPLACE_ME":
        pytest.skip("No token configured in config/vault.yaml")
    result = check_vault_token(VAULT_URL, token, name="live-token")
    assert result["error"] is None, f"Unexpected error: {result['error']}"
    assert result["severity"] in ("healthy", "warning", "critical")


@pytest.mark.vault
def test_live_approle_short_ttl():
    _require_healthy_vault()
    cfg = _vault_config()
    role_id = cfg.get("role_id", "")
    secret_id = cfg.get("secret_id", "")
    if not role_id or not secret_id or "REPLACE_ME" in (role_id, secret_id):
        pytest.skip("AppRole credentials not configured in config/vault.yaml")
    result = check_vault_approle(
        VAULT_URL, role_id, secret_id, name="expiry-watcher-test-short-ttl"
    )
    assert result["error"] is None, f"Unexpected error: {result['error']}"
    assert result["days_remaining"] is not None
    assert result["days_remaining"] <= 7, f"Expected critical TTL, got {result['days_remaining']} days"
    assert result["severity"] == "critical"


@pytest.mark.vault
def test_live_secret_id_short_ttl():
    _require_healthy_vault()
    cfg = _vault_config()
    role_name = cfg.get("role_name", "")
    secret_id = cfg.get("secret_id", "")
    lookup_token = cfg.get("lookup_token", "")
    if not role_name or not secret_id or not lookup_token or "REPLACE_ME" in (role_name, secret_id, lookup_token):
        pytest.skip("secret_id-lookup credentials not configured in config/vault.yaml")
    result = check_vault_secret_id(
        VAULT_URL, role_name, secret_id, lookup_token, name="expiry-watcher-test-short-ttl-secret-id"
    )
    assert result["error"] is None, f"Unexpected error: {result['error']}"
    assert result["days_remaining"] is not None
    assert result["days_remaining"] <= 7, f"Expected critical TTL, got {result['days_remaining']} days"
    assert result["severity"] == "critical"
