# Expiry Watcher — Tickets

Thresholds (confirmed): warning ≤ 30 days, critical ≤ 7 days, expired ≤ 0 days.
Scheduler (confirmed): systemd timer.

---

## EW-001 — Repo scaffolding, .gitignore, LICENSE, directory skeleton

**Depends on:** nothing

**Description:**
Establish the repository baseline so all subsequent tickets have a clean
foundation. No application logic. No credentials.

**Acceptance criteria:**
- [x] `.gitignore` excludes at minimum: `.idea/`, `.venv/`, `results.db`,
      `__pycache__/`, `*.pyc`, `*.pyo`, `.env`, `config/vault.yaml`,
      `config/local_*.yaml`
- [x] `LICENSE` present, MIT, copyright Igal Vexler 2026
- [x] `README.md` present as a placeholder (single heading only — content is EW-010)
- [x] Directory skeleton exists (empty `__init__.py` or `.gitkeep` where needed):
      `checker/`, `dashboard/`, `dashboard/templates/`, `config/`, `tests/`, `systemd/`
- [x] `requirements.txt` lists runtime deps with pinned versions:
      `fastapi`, `uvicorn`, `cryptography`, `hvac`, `pyyaml`
- [x] `requirements-dev.txt` lists dev deps with pinned versions:
      `pytest`, `pytest-cov`, `httpx` (for FastAPI test client)
- [x] `config/targets.yaml.example` exists as a template with no real
      hostnames, credentials, or paths — all values are obviously fake
      placeholders (e.g. `vault_url: "http://localhost:8200"`,
      `role_id: "REPLACE_ME"`)
- [x] `git status` after the commit shows a clean tree with no untracked
      surprises and no `.idea/` or `.venv/` files
- [x] First commit lands with all of the above plus PRD.md, TICKETS.md,
      CLAUDE.md — verify with `git log --stat`
      (`PRD.md`/`TICKETS.md` later reorganized into `docs/`; `CLAUDE.md`
      and `README.md` remain at repo root)

---

## EW-002 — `severity.py` — threshold logic

**Depends on:** EW-001

**Description:**
Single module with one pure function. No I/O, no external deps. The
threshold logic every other module imports.

**Acceptance criteria:**
- [x] `checker/severity.py` exports `compute_severity(days_remaining: int) -> str`
- [x] Return values are exactly the strings `"healthy"`, `"warning"`,
      `"critical"`, `"expired"` — no other strings, no variations
- [x] Boundary behaviour (all must be verified by the test suite):

  | `days_remaining` | expected |
  |---|---|
  | -1 | `"expired"` |
  | 0  | `"expired"` |
  | 1  | `"critical"` |
  | 7  | `"critical"` |
  | 8  | `"warning"` |
  | 30 | `"warning"` |
  | 31 | `"healthy"` |
  | 365| `"healthy"` |

- [x] `tests/test_severity.py` covers every row in the table above as a
      named test case — not a single parametrize with unlabelled values
- [x] `pytest tests/test_severity.py -v` passes with 0 failures, 0 errors
- [x] No imports beyond the Python stdlib in `severity.py`

---

## EW-003 — `tls_checker.py` — remote TLS endpoint checks

**Depends on:** EW-002

**Description:**
Check TLS certificates for a list of remote endpoints. Use only stdlib
(`ssl`, `socket`) — no third-party TLS library for the check itself
(`cryptography` is allowed for parsing if needed, but the connection must
use stdlib). Record days remaining and severity.

**Acceptance criteria:**
- [x] `checker/tls_checker.py` exports
      `check_tls(host: str, port: int = 443, timeout: int = 10) -> dict`
- [x] Returned dict contains keys: `host`, `port`, `days_remaining` (int),
      `severity` (str), `checked_at` (ISO-8601 UTC string), `error` (str or None)
- [x] On a healthy domain, `severity` is `"healthy"` and `error` is `None`
- [x] On `expired.badssl.com`, `severity` is `"expired"` and
      `days_remaining` is ≤ 0 — **this must be run and the actual output
      shown, not assumed**
- [x] On a connection failure or timeout, `error` is a non-empty string,
      `days_remaining` is `None`, `severity` is `None`
- [x] `tests/test_tls_checker.py` covers:
      - at least one healthy domain (a domain that will stay healthy —
        not a personal domain; e.g. `google.com`)
      - `expired.badssl.com` — asserts `severity == "expired"` and
        `days_remaining <= 0`
      - a hostname that doesn't resolve — asserts `error` is not None
- [x] Tests that hit the network are marked `@pytest.mark.network` so CI
      can skip them when network is unavailable
- [x] `pytest tests/test_tls_checker.py -v -m "not network"` passes (the
      offline/error-path tests must not require network)
- [x] `pytest tests/test_tls_checker.py -v -m network` passes when run
      with a live internet connection — Developer must run this and show output

---

## EW-004 — `local_cert_checker.py` — local certificate file checks

**Depends on:** EW-002

**Description:**
Check PEM/DER certificate files on the local filesystem. Uses the
`cryptography` library to parse cert files. Test fixtures are
machine-generated with obviously fake identifiers — never real certs.

**Acceptance criteria:**
- [x] `checker/local_cert_checker.py` exports
      `check_cert_file(path: str) -> dict`
- [x] Returned dict contains keys: `path`, `days_remaining` (int),
      `severity` (str), `checked_at` (ISO-8601 UTC string), `error` (str or None)
- [x] Test fixtures live in `tests/fixtures/`:
      - `valid_cert.pem` — self-signed, CN=valid-test-cert.invalid,
        expiry ≥ 90 days from generation date
      - `expired_cert.pem` — self-signed, CN=expired-test-cert.invalid,
        `notAfter` set to a date in the past (e.g. 2020-01-01)
      - Both generated by the test setup or a checked-in generation
        script — **neither is a real production cert**
- [x] `check_cert_file("tests/fixtures/valid_cert.pem")` returns
      `severity == "healthy"`
- [x] `check_cert_file("tests/fixtures/expired_cert.pem")` returns
      `severity == "expired"` and `days_remaining <= 0` — **run and show output**
- [x] `check_cert_file("/nonexistent/path.pem")` returns a non-empty
      `error` string, `days_remaining` is `None`
- [x] `tests/test_local_cert_checker.py` covers all three cases above,
      plus one near-expiry fixture (≤ 7 days) asserting `severity == "critical"`
- [x] `pytest tests/test_local_cert_checker.py -v` passes with 0 failures,
      0 errors — no network required
- [x] Fixtures are committed to git (they contain no secrets — only fake
      test CN values and public-key material)

---

## EW-005 — `vault_checker.py` — Vault TTL checks

**Depends on:** EW-002

**Description:**
Check Vault AppRole `secret_id` TTL and token TTL against a real running
Vault instance (the existing Vault Secrets Demo). Credentials read from
`config/vault.yaml` (gitignored). Reuses the hvac AppRole pattern already
established in that project.

For the deliberate-short-TTL test, a **new** AppRole role named
`expiry-watcher-test-short-ttl` is created in the existing Vault instance.
This role is completely separate from the Vault Secrets Demo's `demo-app`
role — it must not share a `role_id`, `secret_id`, or policy with it.
The separation keeps the Vault project's own demo state clean and makes
the test's intent explicit.

**Prerequisite check (mandatory before any live Vault work):**

`vault_checker.py` must export a `check_vault_health(vault_url: str) -> dict`
function that:
- Calls `GET <vault_url>/v1/sys/health`
- Returns `{"reachable": True, "sealed": False}` when Vault is up and unsealed
- Returns `{"reachable": False, "sealed": None, "error": "<message>"}` when
  unreachable
- Returns `{"reachable": True, "sealed": True, "error": "Vault is sealed"}` when
  sealed

Any live test (marked `@pytest.mark.vault`) must call `check_vault_health()`
first and skip with a clear message if it fails:

```
pytest.skip(
    "Vault is not reachable or is sealed. "
    "Start it with: docker compose -f ../vault-secrets-demo/docker-compose.yml up vault -d "
    "&& bash ../vault-secrets-demo/scripts/unseal.sh"
)
```

`check.py` (EW-006) must similarly call `check_vault_health()` before
attempting any Vault checks and write a structured error to the db (not
crash) if the health check fails.

**Acceptance criteria:**
- [x] `checker/vault_checker.py` exports:
      - `check_vault_health(vault_url: str) -> dict` (see spec above)
      - `check_vault_token(vault_url: str, token: str) -> dict`
      - `check_vault_approle(vault_url: str, role_id: str, secret_id: str) -> dict`
- [x] Each result dict from `check_vault_token` / `check_vault_approle`
      contains: `name` (str), `type` (str), `days_remaining` (float rounded
      to 2dp), `severity` (str), `checked_at` (ISO-8601 UTC string),
      `error` (str or None)
- [x] A `scripts/vault_setup_test_role.sh` script (committed, no secrets
      hardcoded) creates the `expiry-watcher-test-short-ttl` AppRole in the
      running Vault instance with `token_ttl=6d` (≤ 7 days → `"critical"`).
      The script prints the generated `role_id` and `secret_id` to stdout
      for the user to copy into `config/vault.yaml` — it does not write
      them anywhere automatically
- [x] `check_vault_token` against a token with a known TTL > 30 days
      returns `severity == "healthy"` — shown with actual output
- [x] `check_vault_approle` against the `expiry-watcher-test-short-ttl`
      role (TTL ≤ 7 days) returns `severity == "critical"` — **shown
      with actual Vault output, not assumed**
- [x] On Vault unreachable, `check_vault_health` returns `reachable: false`;
      `check_vault_token` / `check_vault_approle` return `error` non-empty,
      `days_remaining` None
- [x] No credentials appear in any test file, test output, log line, or
      script — only `vault_url` is acceptable as plaintext
- [x] `tests/test_vault_checker.py`:
      - offline tests mock the hvac client and the health endpoint; cover:
        healthy TTL, near-expiry TTL, unreachable Vault, sealed Vault
      - live tests marked `@pytest.mark.vault`; each begins with the
        `check_vault_health()` prerequisite skip guard described above
- [x] `pytest tests/test_vault_checker.py -v -m "not vault"` passes
      without a running Vault instance
- [x] `pytest tests/test_vault_checker.py -v -m vault` passes against the
      live Vault Secrets Demo instance — Developer runs this, shows full
      pytest output AND the `journalctl` / `vault token lookup` output that
      confirms the short-TTL role's actual TTL

---

## EW-006 — `db.py` + `check.py` orchestration

**Depends on:** EW-003, EW-004, EW-005

**Description:**
Wire the three checkers together into a single run. Write all results plus
a run timestamp to SQLite. `db.py` owns the schema and all read/write
helpers. `check.py` is the entry point — reads `config/targets.yaml`,
calls checkers, writes results.

**Acceptance criteria:**
- [x] `checker/db.py` exports:
      - `init_db(path: str)` — creates the schema if it doesn't exist
      - `write_results(path: str, results: list[dict])` — upserts results
        + sets `last_checked` timestamp
      - `read_results(path: str) -> list[dict]`
      - `get_last_checked(path: str) -> datetime | None`
- [x] SQLite schema has at minimum: `id`, `name`, `type`, `days_remaining`,
      `severity`, `checked_at`, `error`
- [x] `checker/check.py` is a runnable script (`python checker/check.py`):
      - reads `config/targets.yaml`
      - runs all enabled checkers
      - writes to `results.db` (path configurable via env var or arg)
      - exits 0 on completion (checker errors are written to the db,
        not raised as process-level failures)
- [x] After a run of `check.py` against real test targets, `read_results()`
      returns at least one row per enabled target — **verified by actually
      running it and printing results**
- [x] `tests/test_db.py` covers `init_db`, `write_results`, `read_results`,
      `get_last_checked` using an in-memory SQLite (`":memory:"`), not a
      real file — no I/O side-effects in tests
- [x] `pytest tests/test_db.py -v` passes with 0 failures, 0 errors
- [x] `results.db` does not appear in `git status` after a run (covered by
      `.gitignore` from EW-001)

---

## EW-007 — systemd timer + service

**Depends on:** EW-006

**Description:**
Install and verify the systemd units that run `check.py` on a schedule.
This ticket is not done until the timer has actually fired and the service
has run — not just that the unit files look correct.

**Acceptance criteria:**
- [x] `systemd/expiry-watcher.service` runs `check.py` from the correct
      working directory with the correct Python interpreter (from `.venv`)
- [x] `systemd/expiry-watcher.timer` triggers the service; default interval
      is 6 hours, configurable by editing the unit file
- [x] `systemd/install.sh` (or inline instructions in README) copies units
      to `~/.config/systemd/user/`, runs `systemctl --user daemon-reload`,
      enables and starts the timer
- [x] `systemctl --user status expiry-watcher.timer` shows `active (waiting)`
      — verified with actual command output shown
- [x] `systemctl --user start expiry-watcher.service` triggers a manual run
      that completes successfully and writes to `results.db`
      — verified with `journalctl --user -u expiry-watcher.service` output shown
- [x] `journalctl` output contains no credential strings
- [x] `systemctl --user stop expiry-watcher.timer` stops future runs cleanly
- [x] Unit files are committed; `results.db` is not

---

## EW-008 — `dashboard/main.py` — FastAPI read-only status dashboard

**Depends on:** EW-006

**Description:**
A separate FastAPI process that reads `results.db` and serves a status
page. Strictly read-only — it never writes to the database. Staleness
detection: if `last_checked` is older than 2× the check interval (12h),
the dashboard visibly flags itself as stale.

**Acceptance criteria:**
- [x] `dashboard/main.py` is a runnable FastAPI app
- [x] `GET /status` returns JSON: list of all monitored items, each with
      `name`, `type`, `days_remaining`, `severity`, `checked_at`, `error`
      — plus a top-level `last_checked` timestamp and `stale: bool`
- [x] `GET /` returns an HTML table, color-coded by severity:
      healthy=green, warning=amber, critical/expired=red
- [x] HTML page shows "Last checked: X minutes ago" and turns visually
      distinct (e.g. banner, red border) when `stale == true`
- [x] No code path in `dashboard/` calls any write function — confirmed by
      code review and by a test that monkeypatches `write_results` to raise
      and confirms no dashboard endpoint triggers it
- [x] `tests/test_dashboard.py` uses FastAPI's `TestClient` (via httpx):
      - `GET /status` returns 200 with correct JSON shape
      - `GET /` returns 200 with HTML containing severity classes
      - Staleness: seed `results.db` with an old `last_checked` timestamp,
        assert `stale == true` in the response
      - Read-only: assert no write function is called during any request
- [x] `pytest tests/test_dashboard.py -v` passes with 0 failures
- [x] `docker-compose.yml` starts the dashboard successfully
      (`docker compose up dashboard` → `GET /` returns 200)
      — verified with actual `curl` output shown
- [x] `docker-compose.yml` mounts the host `results.db` into the container
      at the path the dashboard reads from, explicitly — e.g.:
      ```yaml
      volumes:
        - ./results.db:/app/results.db:ro
      ```
      The `:ro` flag is required (dashboard is read-only; enforce it at
      the mount level too). The host path must be the same file `check.py`
      writes to, not a copy or a separately-named file
- [x] Cross-process read verified end-to-end: run `python checker/check.py`
      on the host (simulating the systemd service), then immediately call
      `GET /status` on the running dashboard container and confirm the
      response contains rows from that run — verified by showing the
      `check.py` run output, the `curl /status` response, and confirming
      at least one `checked_at` timestamp in the JSON matches the
      just-completed run. "Both reference results.db by name" is not
      sufficient — the file must be the same inode on disk

---

## EW-009 — CI pipeline (GitHub Actions)

**Depends on:** EW-008

**Description:**
GitHub Actions workflow that runs on every push and PR. Network-dependent
tests (TLS live, Vault live) are skipped in CI; everything else must pass.

**Acceptance criteria:**
- [x] `.github/workflows/ci.yml` exists and runs on `push` and
      `pull_request` to `main`
- [x] CI steps: checkout → set up Python → install deps (both
      `requirements.txt` and `requirements-dev.txt`) → run pytest with
      `-m "not network and not vault"`
- [x] CI passes on a clean push with no local state — verified by pushing
      and reading the actual Actions run result, not just the local run
- [x] CI run URL is recorded in the ticket acceptance sign-off comment
- [x] No secrets or vault credentials appear in the CI workflow file or
      in any CI log — confirmed by reading the raw job log
- [x] Badge added to README.md placeholder (EW-010 will flesh out the rest)

---

## EW-010 — README

**Depends on:** EW-009

**Description:**
Complete the README. Honest about what's tested, what runs on Linux only,
and what's explicitly out of scope (AWS). Same honesty standard as the
Vault Secrets Demo README.

**Acceptance criteria:**
- [x] Sections: What this is / Architecture (diagram) / Setup / Running
      the checker / Running the dashboard / Running tests / Platform support
      / What's not in scope
- [x] Architecture section accurately reflects the two-process split and
      explains why (not just what)
- [x] Setup section covers: clone → create `.venv` → `pip install` →
      copy `config/targets.yaml.example` to `config/targets.yaml` and fill
      in values → (optionally) install systemd units
- [x] Platform support section is explicit: tested on Linux; macOS and
      Windows are untested; systemd units are Linux-only
- [x] "What's not in scope" section references EW-012 (AWS) as a stretch
      ticket, not a supported feature
- [x] Fresh-clone smoke test performed by Developer: follow the README
      from a clean directory, confirm each step works as written
- [x] No placeholder text, no "TODO" lines left in the final README

---

## EW-011 — Pre-publish security/sanity audit

**Depends on:** EW-010

**This ticket belongs to the user alone. It is not delegatable.**

**Checklist (to be performed personally):**
- [x] `git log --all --full-history -- '*.yaml' '*.env' '*.json'`
      — confirm no credential file was ever committed, even in an earlier
      commit that was later deleted
- [x] `git log -p | grep -iE 'password|secret|token|role_id|secret_id'`
      — scan full patch history for accidental credential strings
- [x] Clean-clone smoke test from a fresh directory: clone the repo,
      follow the README exactly, confirm checker runs and dashboard serves
- [x] Manual run-through: confirm all six known states produce correct
      output (healthy cert, expired cert via badssl, healthy local cert,
      expired local cert, healthy Vault token, near-expiry Vault token)
- [x] Confirm `results.db` is not present in the published repo
- [x] Confirm CI badge is green on `main`

---

## EW-012 (stretch) — AWS IAM key age checker

**Depends on:** EW-001 (can be implemented independently of EW-002–EW-010)

**Status: DEFERRED** — not part of v1. To be implemented only when real
AWS credentials are available for testing. A checker that has never
actually checked an AWS key is unproven.

**When unblocked, acceptance criteria will include:**
- `checker/aws_checker.py` using `boto3`
- Live test against a real IAM key with a known creation date
- Mutation test: a key older than the warning threshold is correctly flagged
- README Platform support section updated

---

## EW-013 — Home lab deployment documentation

**Goal:** Document deployment on a Proxmox home lab environment,
including Vault integration and multi-project coexistence.

**Deliverables:**
- `docs/HOMELAB_DEPLOYMENT.md` — full deployment walkthrough for
  Proxmox VE + Ubuntu Server VM environment
- README platform support section updated with home lab notes
- Vault integration steps documented (vault_setup_test_role.sh)
- Multi-project coexistence documented (ports, Portainer visibility)
- Discovered and documented: `python3.12-venv` not installed by
  default on Ubuntu Server

**Tested on:**
- Proxmox VE 9.2.3, Beelink SER mini PC
- Ubuntu Server 24.04.3 LTS VM
- Docker 29.6.0, Python 3.12

**Dependencies:** EW-010, EW-011

**Status: DONE**

---

## EW-014 — Vault AppRole `secret_id` TTL check

**Depends on:** EW-005

**Description:**
`check_vault_approle()` (EW-005) performs a real AppRole login and reports
the resulting **token's** `lease_duration` — fixed by the role's
`token_ttl=6d`. It never inspects the **`secret_id` credential's own TTL**.
`scripts/vault_setup_test_role.sh` never sets `secret_id_ttl` on the role
either, so the `secret_id` inherits Vault's unbounded default. Net effect:
no advance warning that the `secret_id` itself is stale or long-lived,
right up until it's revoked or breaks. This is a separately-scoped
detection gap, not a bug in the existing check — `docs/SPEC.md` documents
the existing check's scope as intentional.

Uses `hvac`'s `auth.approle.read_secret_id(role_name, secret_id)`, a
real Vault lookup against `auth/approle/role/<role_name>/secret-id/lookup`
(a **POST**-based read-only endpoint — requires a token with `update`
capability on that specific path, per Vault's ACL model). This is **not**
the AppRole `role_id`/`secret_id` login flow and must use a separate,
narrowly-scoped credential — never conflated with the login pair.

**Acceptance criteria:**
- [x] `checker/vault_checker.py` exports
      `check_vault_secret_id(vault_url: str, role_name: str, secret_id: str, lookup_token: str, name: str = "vault-secret-id") -> dict`,
      same result shape as the existing checks (`name`, `type`,
      `days_remaining`, `severity`, `checked_at`, `error`)
- [x] Uses a Vault token (`lookup_token`) with `update` capability scoped
      to exactly `auth/approle/role/<role_name>/secret-id/lookup` — not
      root/admin-equivalent, not reused from or conflated with the
      `role_id`/`secret_id` login pair
- [x] `days_remaining` computed from `secret_id_ttl` (seconds), same
      `round(ttl_seconds / 86400, 2)` convention, fed through the existing
      `compute_severity()` — no new threshold logic
- [x] `secret_id_ttl` unset/0 → `severity: "healthy"`, `days_remaining: None`,
      matching the existing `ttl == 0` pattern in `check_vault_token` /
      `check_vault_approle`
- [x] Wired into `check.py`'s `_run_vault_checks()`, gated independently
      (skips cleanly if `role_name`/`secret_id`/`lookup_token` missing or
      `REPLACE_ME`, consistent with the existing gates)
- [x] `config/vault.yaml.example` documents the two new fields
      (`role_name`, `lookup_token`), clearly distinguished from the
      login pair
- [x] `scripts/vault_setup_test_role.sh` extended (script-driven, not
      manual out-of-band setup) to: mint a dedicated test `secret_id` with
      a per-secret-id `ttl=5d` override (Vault's actual API parameter
      name — `secret_id_ttl` is silently ignored as unrecognized; leaving
      the role's
      `token_ttl=6d` and any other already-issued `secret_id` untouched),
      write a minimal named Vault policy scoped to exactly one role's
      lookup path, and mint a `lookup_token` bound to that policy — all
      printed to stdout for the user to copy into `config/vault.yaml`,
      same convention as the existing credentials, never auto-written to
      any file. Must not touch vault-secrets-demo's `demo-app` role.
- [x] Both directions proven with real Vault output shown, not assumed:
      a normal/long-lived `secret_id` reports `"healthy"`; the
      deliberately short-TTL (`5d`) `secret_id` reports `"critical"`
- [x] Blast-radius check: before/after Vault output (via
      `secret-id-accessor/lookup` or equivalent) confirming `secret_id_ttl`
      is not silently capped by any mount-level setting shared with
      vault-secrets-demo's `demo-app` role — pasted into the QA report,
      not assumed
- [x] `tests/test_vault_checker.py`: offline mocked tests (healthy,
      near-expiry/critical, warning-band, no-expiration, Vault error) +
      one live test marked `@pytest.mark.vault` with the
      `check_vault_health()` skip guard, matching the existing file's
      pattern exactly
- [x] No credentials in any test file, test output, log line, or script
      output
- [x] `docs/SPEC.md` updated with the new function's mechanics, contrasted
      explicitly against `check_vault_approle` (login-token lease vs.
      credential's own TTL; consumes a login vs. read-only lookup)
- [x] `README.md` updated (Vault credential setup section) if the new
      fields or check change what's exercised
- [x] `dashboard/` untouched — zero files under `dashboard/` in
      `git diff --stat`

**Status: DONE**

---

## Ticket status

| Ticket | Title | Status |
|---|---|---|
| EW-001 | Repo scaffolding | DONE |
| EW-002 | severity.py | DONE |
| EW-003 | tls_checker.py | DONE |
| EW-004 | local_cert_checker.py | DONE |
| EW-005 | vault_checker.py | DONE |
| EW-006 | db.py + check.py | DONE |
| EW-007 | systemd timer | DONE |
| EW-008 | dashboard | DONE |
| EW-009 | CI pipeline | DONE |
| EW-010 | README | DONE |
| EW-011 | Security audit | DONE (user only) |
| EW-012 | AWS IAM (stretch) | DEFERRED |
| EW-013 | Home lab deployment documentation | DONE |
| EW-014 | Vault AppRole secret_id TTL check | DONE |
