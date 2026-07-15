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
    docker exec -i \
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

# --- EW-014: secret_id-lookup credential + a deliberately short-TTL secret_id ---
# This is a SEPARATE credential pair from role_id/secret_id above. It authenticates
# with a bearer token + narrow ACL policy, not the AppRole login flow, and must
# never be conflated with it.

LOOKUP_POLICY="expiry-watcher-secret-id-lookup"

echo ""
echo "Writing narrow lookup policy: ${LOOKUP_POLICY}"
vault_exec policy write "${LOOKUP_POLICY}" - <<EOF
path "auth/approle/role/${ROLE_NAME}/secret-id/lookup" {
  capabilities = ["update"]
}
EOF

echo "Minting lookup_token bound to ${LOOKUP_POLICY} only..."
LOOKUP_TOKEN=$(vault_exec token create -policy="${LOOKUP_POLICY}" -ttl=90d -field=token)

echo "Minting a dedicated short-TTL secret_id (ttl=5d, lands in the 'critical' band)..."
# NOTE: the Vault API parameter is `ttl`, not `secret_id_ttl` — the latter is
# silently ignored as an unrecognized field and the secret_id comes back unbounded.
# Confirmed live against this instance's shared approle mount (max_lease_ttl=2160h/90d):
# a requested ttl above 90d is silently capped to exactly 90d, so keep this well under it.
SHORT_TTL_SECRET_ID=$(vault_exec write -field=secret_id "auth/approle/role/${ROLE_NAME}/secret-id" ttl=5d)

echo ""
echo "=== Copy the following ADDITIONAL fields into config/vault.yaml (for check_vault_secret_id) ==="
echo ""
echo "  role_name: \"${ROLE_NAME}\""
echo "  secret_id: \"${SHORT_TTL_SECRET_ID}\"   # replaces the secret_id above — now carries a 5d ttl"
echo "  lookup_token: \"${LOOKUP_TOKEN}\""
echo ""
echo "=== secret_id_ttl read-back, using the lookup_token itself (self-verifying: proves both the ttl=5d value and the lookup_token's policy work) ==="
docker exec \
    -e VAULT_ADDR="$VAULT_ADDR" \
    -e VAULT_TOKEN="$LOOKUP_TOKEN" \
    "$VAULT_CONTAINER" vault write "auth/approle/role/${ROLE_NAME}/secret-id/lookup" secret_id="${SHORT_TTL_SECRET_ID}"
