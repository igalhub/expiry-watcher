# SPEC — Expiry Watcher

Technical spec of the current implementation. `docs/PRD.md` covers the
problem/goals; this covers module interfaces, data shapes, and exact
per-checker mechanics.

---

## Module map

```
checker/severity.py            pure function, no I/O
checker/tls_checker.py           remote TLS endpoint cert expiry (stdlib ssl/socket + cryptography)
checker/local_cert_checker.py    on-disk cert file expiry (cryptography)
checker/vault_checker.py         Vault health/token-TTL/AppRole-lease checks (hvac + requests)
checker/db.py                    SQLite persistence
checker/check.py                 entry point, wires config → checkers → db
dashboard/main.py                FastAPI read-only dashboard
```

## `checker/severity.py`

```python
compute_severity(days_remaining: int) -> str
```

The only severity rule in the whole codebase — every checker imports
this rather than duplicating thresholds:

| `days_remaining` | Severity |
|---|---|
| `<= 0` | `expired` |
| `<= 7` | `critical` |
| `<= 30` | `warning` |
| else | `healthy` |

Note this is a plain function with hardcoded boundaries, not a
config-driven system like docker-sentinel's `severity.py` — thresholds
here are fixed by design (cert/credential expiry windows don't vary per
deployment the way container health thresholds do).

## `checker/tls_checker.py`

```python
check_tls(host: str, port: int = 443, timeout: int = 10) -> dict
```

Connects with `ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)`,
**`check_hostname = False`, `verify_mode = ssl.CERT_NONE`** — TLS
verification is deliberately disabled. This is not a bug: the whole
point is reading the certificate's expiry even when it's already
expired or hostname-mismatched, which is exactly the failure case this
tool exists to catch. A verifying context would raise instead of
returning a result for the most interesting inputs. Parses the DER cert
via `cryptography.x509.load_der_x509_certificate`, reads
`not_valid_after_utc`. Any exception (connection refused, timeout, TLS
handshake failure, malformed cert) is caught and returned as
`{"days_remaining": None, "severity": None, "error": str(e)}` — never
raises out of the function.

## `checker/local_cert_checker.py`

```python
check_cert_file(path: str) -> dict
```

Same shape as `check_tls`, but reads a local PEM file directly
(`x509.load_pem_x509_certificate(Path(path).read_bytes())`) — no
socket/TLS handshake involved, so `ssl.SSLContext` doesn't apply here.
Same catch-all exception handling, same return shape.

## `checker/vault_checker.py`

Four independent functions, all returning the same result shape
(`name`, `type`, `days_remaining`, `severity`, `checked_at`, `error`):

- **`check_vault_health(vault_url)`** — `GET /v1/sys/health`. A `503`
  response means Vault is sealed (Vault's own health-check convention);
  a connection failure means unreachable. This gates the other three
  checks — see `check.py`'s `_run_vault_checks`.
- **`check_vault_token(vault_url, token, name)`** — `client.auth.token.lookup_self()`,
  reads `ttl` (seconds) from the response. `ttl == 0` means the token
  never expires (e.g. a root token) and is reported `healthy` with
  `days_remaining=None`, not run through `compute_severity`.
- **`check_vault_approle(vault_url, role_id, secret_id, name)`** —
  performs an actual AppRole login (`client.auth.approle.login`) and
  reads the resulting token's `lease_duration`. This is a real login
  call, not a read-only inspection — every check run consumes one
  AppRole login. Same `ttl == 0` → healthy/`None` handling as the token
  check.
- **`check_vault_secret_id(vault_url, role_name, secret_id, lookup_token, name)`**
  (EW-014) — reports the **`secret_id` credential's own remaining TTL**,
  not the login token's lease that `check_vault_approle` already covers.
  Calls `client.auth.approle.read_secret_id(role_name, secret_id)`, a
  **read-only** lookup against Vault's `auth/approle/role/<role_name>/secret-id/lookup`
  endpoint — this is a POST under the hood, so it requires a Vault token
  with `update` (not `read`) ACL capability on that specific path. That
  token (`lookup_token`) is a distinct credential from the AppRole
  `role_id`/`secret_id` login pair — it authenticates as a bearer token
  scoped by a narrow named policy, never derived from or interchangeable
  with the login flow. Unlike `check_vault_approle`, this call does not
  consume or rotate the `secret_id` — it's a pure read. Reads
  `secret_id_ttl` (seconds) from the response; same `ttl == 0` →
  healthy/`None` handling as the other two TTL checks. Requires `role_name`
  (the AppRole's name, distinct from the `role_id` UUID used for login).

**Confirmed constraint (live-verified, EW-014):** on this project's shared
Vault dev instance, the `approle` auth mount's `max_lease_ttl` (2160h/90d)
caps `secret_id` `ttl` requests the same way it caps login-token leases —
requesting `ttl=120d` when minting a `secret_id` returns exactly `90d`,
silently capped, not rejected. See `docs/HOMELAB_DEPLOYMENT.md` for the
full finding; keep any `secret_id` `ttl` used for testing well under 90d
on this shared instance.

Days-remaining values for Vault are `ttl_seconds / 86400` rounded to 2
decimal places (fractional days are meaningful at Vault's typical
hour-to-day TTL scale, unlike cert expiry which is whole days).

## `checker/db.py`

```sql
CREATE TABLE IF NOT EXISTS results (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    type           TEXT NOT NULL,
    days_remaining INTEGER,
    severity       TEXT,
    checked_at     TEXT NOT NULL,
    error          TEXT,
    UNIQUE(name, type)
);

CREATE TABLE IF NOT EXISTS metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

Upsert key is `(name, type)` — e.g. `("vault", "vault-health")` or a
hostname + `"tls"`. `metadata` is a single-row-per-key table used to
store `last_checked` (updated every run, independent of whether any
individual check's `days_remaining` changed) — this is what the
dashboard's staleness check reads, not `MAX(checked_at)` over `results`,
so a run that writes zero results (e.g. all checks errored) still
updates the staleness clock correctly.

## `checker/check.py` (entry point)

```
python -m checker.check [--config config/targets.yaml] [--db results.db]
```

Sequence: load `config/targets.yaml` (exit 1 if missing/empty) → `init_db` →
run TLS checks → run local-cert checks → run Vault checks (only if a
`vault:` section exists in config) → `write_results` → print a one-line
summary. Every checker function already catches its own exceptions, so
`main()` itself has no try/except around the check calls — a single
misbehaving check can't take down the rest of the run.

**Vault credential resolution:** `config/vault.yaml` (gitignored) is
tried first; if it doesn't exist, falls back to the `vault:` section of
`targets.yaml` itself (useful for environments with no secrets file at
all). Credential values equal to the literal string `"REPLACE_ME"` are
treated as "not configured" and that check is skipped rather than run
with a placeholder — this is what lets `config/targets.yaml.example`
ship a Vault URL by default without accidentally trying to log in with
example placeholder credentials.

If Vault is unreachable or sealed, `_run_vault_checks` short-circuits
and writes a single `vault-health` error row rather than attempting the
token/AppRole checks (which would just fail anyway) — printed as a
`WARNING` to stderr, not treated as a fatal error for the whole run.

## `dashboard/main.py`

Read-only against `results.db` — no `write_results` import anywhere in
`dashboard/`. `GET /status` (JSON: all rows + severity + staleness) and
`GET /` (HTML, Tabler-icon severity badges, color-coded by the same
`_SEVERITY_BADGE`/`_SEVERITY_COUNT_CLASS`/`_SEVERITY_ICON` maps for
`healthy`/`warning`/`critical`/`expired`).

Env vars: `EXPIRY_WATCHER_DB` (default `results.db`),
`EXPIRY_WATCHER_CHECK_INTERVAL_HOURS` (default `6`) — staleness
threshold is always `2 ×` this value, matching the checker's systemd
timer interval. `_db_exists()` guards against the dashboard starting
before the checker has ever run (no `results.db` on disk yet) rather
than crashing on a missing file.

## Test split

Tests marked `network`/`vault` require live targets and are excluded
from CI (`pytest -m "not network and not vault" -v`); everything else
runs offline against mocks or fixtures. `tests/fixtures/*.pem` are
synthetic self-signed certs generated by
`scripts/generate_test_fixtures.py` — not real certificates.
