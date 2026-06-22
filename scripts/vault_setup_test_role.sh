#!/usr/bin/env bash
# Creates the expiry-watcher-test-short-ttl AppRole in the running Vault instance.
# Requires: Docker, vault container named 'vault' running and unsealed,
#           VAULT_TOKEN set to a root or admin token.
# Usage: export VAULT_TOKEN=<root-token> && bash scripts/vault_setup_test_role.sh
set -euo pipefail

if [ -z "${VAULT_TOKEN:-}" ]; then
    echo "ERROR: VAULT_TOKEN is not set." >&2
    echo "       export VAULT_TOKEN=<root-token> before running this script." >&2
    exit 1
fi

ROLE_NAME="expiry-watcher-test-short-ttl"
VAULT_CONTAINER="vault"
VAULT_ADDR="http://127.0.0.1:8200"

vault_exec() {
    docker exec \
        -e VAULT_ADDR="$VAULT_ADDR" \
        -e VAULT_TOKEN="$VAULT_TOKEN" \
        "$VAULT_CONTAINER" vault "$@"
}

echo "Vault address : $VAULT_ADDR (via container: $VAULT_CONTAINER)"
echo "Role name     : $ROLE_NAME"
echo ""

# Enable AppRole auth method (safe to run if already enabled)
vault_exec auth enable approle 2>/dev/null || true

# Create the role. token_ttl=6d puts the resulting token firmly in the 'critical'
# band (1–7 days), which is what the EW-005 live test asserts.
vault_exec write "auth/approle/role/${ROLE_NAME}" \
    token_ttl=6d \
    token_max_ttl=7d \
    token_policies=default

echo "Role written. Fetching credentials..."
echo ""

ROLE_ID=$(vault_exec read -field=role_id "auth/approle/role/${ROLE_NAME}/role-id")
SECRET_ID=$(vault_exec write -field=secret_id -f "auth/approle/role/${ROLE_NAME}/secret-id")

echo "=== Copy the following into config/vault.yaml ==="
echo ""
echo "vault:"
echo "  url: \"http://localhost:8200\""
echo "  role_id: \"${ROLE_ID}\""
echo "  secret_id: \"${SECRET_ID}\""
echo "  token: \"REPLACE_ME\"   # optional: set to a long-lived token to test check_vault_token"
echo ""
echo "=== Role details (confirm token_ttl = 6d) ==="
vault_exec read "auth/approle/role/${ROLE_NAME}"
