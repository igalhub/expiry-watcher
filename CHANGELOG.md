# Changelog — Expiry Watcher

All entries correspond to accepted tickets. Dates reflect the commit date.

---

## EW-016 — Fix `check_vault_secret_id()` to use live `expiration_time`
**Accepted:** 2026-07-15 · commit `4d19f3c`

`check_vault_secret_id()` (EW-014) computed `days_remaining` from Vault's
`secret_id_ttl` field — a static configured duration that never changes
as time passes. Confirmed live during EW-015's QA: it returned exactly
`5.0` days both immediately after minting and 27 minutes later, while
actual time-to-expiration had already dropped to `4.98`. This meant the
check never showed warning→critical progression as a `secret_id` ages —
a flat reading until the credential failed outright, defeating the
purpose of EW-014. Fix computes `days_remaining` from
`(expiration_time - now) / 86400` instead; `secret_id_ttl == 0` stays
the unbounded/healthy gate, unchanged. New offline test proves the value
is a live countdown by patching `datetime.now` to two values a day apart
against a fixed `expiration_time`, asserting the difference — a live
wall-clock sleep test can't prove this (movement at typical short TTLs
is below 2-decimal rounding). Mutation-tested: reverted to the old
calculation, confirmed the new test fails, restored, confirmed it passes
again. `docs/TICKETS.md`'s EW-014 section left untouched except for an
additive forward-reference note. Scope confined to
`checker/vault_checker.py`, `tests/test_vault_checker.py`, `docs/SPEC.md`
— `dashboard/` and the `lookup_token`/`role_name` credential design
untouched.

---

## EW-015 — Fix `days_remaining` precision truncation in `db.py`
**Accepted:** 2026-07-15 · commit `f93acbb`

`checker/db.py`'s `write_results()` forced `days_remaining` through `int()`
before binding it for the SQLite `INSERT`, silently discarding the
2-decimal precision `checker/vault_checker.py` (EW-005/EW-014) deliberately
produces and `docs/SPEC.md` says matters at Vault's hour-to-day TTL scale —
a credential with `6.23` days remaining was stored and displayed as `6`.
No schema change needed: SQLite's `INTEGER` column affinity only converts
a `REAL` to `INTEGER` when the conversion is lossless, so removing the
`int()` cast and binding the raw value is sufficient — verified in-memory
against the exact live schema before implementing, and end-to-end against
the real config afterward. Severity classification is unaffected (already
computed on an internally-`int()`-truncated value by each checker before
returning). New tests in `tests/test_db.py` cover both the fractional
round-trip (`6.23`) and a whole-day `int` regression guard. Scope confined
to `checker/db.py`, `tests/test_db.py`, `docs/SPEC.md` — `dashboard/` and
all other checker modules untouched.

---

## EW-014 — Vault AppRole `secret_id` TTL check
**Accepted:** 2026-07-15 · commit `58e269c`

`checker/vault_checker.py` exports `check_vault_secret_id(vault_url, role_name,
secret_id, lookup_token, name) -> dict`, closing the gap left by
`check_vault_approle` (EW-005), which only ever reported the login token's
lease TTL, never the `secret_id` credential's own TTL. Uses a read-only
lookup (`auth/approle/role/<role_name>/secret-id/lookup`) authenticated by a
narrowly-scoped `lookup_token` — a distinct credential from the
`role_id`/`secret_id` login pair, never conflated with it.
`scripts/vault_setup_test_role.sh` now mints that `lookup_token` (bound to a
policy scoped to exactly one path) and a dedicated `ttl=5d` test `secret_id`,
script-driven end-to-end. Both directions proven with real Vault output:
healthy (unbounded `secret_id`) → `"healthy"`; the `5d` test `secret_id` →
`"critical"`. Confirmed live: the shared `approle` auth mount's
`max_lease_ttl` (90d) caps `secret_id` `ttl` the same way it caps
login-token leases — documented in `docs/HOMELAB_DEPLOYMENT.md` and
`docs/SPEC.md`; not a blocker since the test value (5d) is far under the
cap. `dashboard/` confirmed untouched.

---

## EW-013 — Home lab deployment documentation
**Accepted:** 2026-06-26

`docs/HOMELAB_DEPLOYMENT.md` — full deployment walkthrough for Proxmox VE +
Ubuntu Server VM environment. README platform support section updated with
home lab notes. Vault integration steps documented
(`vault_setup_test_role.sh`). Multi-project coexistence documented (ports,
Portainer visibility). Discovered and documented: `python3.12-venv` not
installed by default on Ubuntu Server. Tested on Proxmox VE 9.2.3
(Beelink SER mini PC), Ubuntu Server 24.04.3 LTS VM, Docker 29.6.0,
Python 3.12.

---

## EW-011 — Pre-publish security/sanity audit
**Accepted:** 2026-06-25 (user only — non-delegatable)

Personal audit performed by Igal Vexler. All six checklist items completed:
- `git log --all --full-history` confirmed no yaml/env/json credential file was
  ever committed in any commit in history.
- Full patch history grep confirmed only code variable names and `REPLACE_ME`
  placeholders — no real credential values.
- `git status --ignored` confirmed `vault.yaml`, `targets.yaml`, and
  `results.db` are correctly excluded by `.gitignore`.
- Fresh-clone smoke test verified at `/tmp/ew-smoketest`: checker runs,
  dashboard serves, README instructions accurate.
- `results.db` absent from the published repo.
- CI badge green on `master`.

Repo confirmed ready to go public.

---

## EW-010 — README
**Accepted:** 2026-06-22 · commit `d09b129`

Complete README covering architecture (two-process split with rationale),
setup, running checker and dashboard, running tests, platform support (Linux
tested; macOS/Windows untested; systemd Linux-only), and scope exclusions
(AWS IAM deferred to EW-012). Fresh-clone smoke test performed.

*Post-acceptance enhancement (2026-06-24):* dark/light mode toggle added to
dashboard; README updated to note the feature and `localStorage` persistence.

---

## EW-009 — CI pipeline (GitHub Actions)
**Accepted:** 2026-06-22 · commit `02b658f`

`.github/workflows/ci.yml` runs on push and pull_request to `master`.
Steps: checkout → Python setup → install deps → pytest with
`-m "not network and not vault"`. 46 offline tests pass. Badge added to
README. CI run verified on a clean push; no secrets in workflow or logs.

---

## EW-008 — FastAPI read-only status dashboard
**Accepted:** 2026-06-22 · commits `547b6a6`, `7160c12`

`dashboard/main.py` — FastAPI app serving `GET /` (HTML, color-coded by
severity) and `GET /status` (JSON). Staleness detection flags data older than
2× check interval. No write path from dashboard to `results.db` — enforced
in code and tested. Docker Compose mounts host `results.db` read-only (`:ro`).
Improved UI with summary cards, severity badges, and Tabler icons.

---

## EW-007 — systemd timer + service
**Accepted:** 2026-06-22 · commit `b5edc92`

`systemd/expiry-watcher.service` and `systemd/expiry-watcher.timer` (6-hour
default interval). `systemd/install.sh` installs units to
`~/.config/systemd/user/`. Timer confirmed `active (waiting)` via
`systemctl --user status`; manual service trigger writes to `results.db`
with no credential strings in `journalctl` output.

---

## EW-006 — `db.py` + `check.py` orchestration
**Accepted:** 2026-06-22 · commit `2424ac2`

`checker/db.py` exports `init_db`, `write_results`, `read_results`,
`get_last_checked`; schema: `id`, `name`, `type`, `days_remaining` (INTEGER),
`severity`, `checked_at`, `error`. `checker/check.py` reads
`config/targets.yaml`, runs all enabled checkers, writes results.db. Tests
use in-memory SQLite. `results.db` excluded by `.gitignore`.

---

## EW-005 — `vault_checker.py` — Vault TTL checks
**Accepted:** 2026-06-22 · commit `f9a33ec`

`checker/vault_checker.py` exports `check_vault_health`, `check_vault_token`,
`check_vault_approle`. Dedicated `expiry-watcher-test-short-ttl` AppRole
(separate from Vault Secrets Demo `demo-app` role) with `token_ttl=6d` used
as the near-expiry fixture. Live tests marked `@pytest.mark.vault` with
health-check skip guard. No credentials in any test file or log.

---

## EW-004 — `local_cert_checker.py` — local certificate file checks
**Accepted:** 2026-06-22 · commit `bb08e01`

`checker/local_cert_checker.py` exports `check_cert_file(path) -> dict`.
Test fixtures in `tests/fixtures/`: `valid_cert.pem` (CN=valid-test-cert.invalid,
≥90d expiry), `expired_cert.pem` (CN=expired-test-cert.invalid, notAfter
in past), dynamic near-expiry cert generated at test time. Both directions
verified: healthy → `"healthy"`, expired → `"expired"` with `days_remaining ≤ 0`.

---

## EW-003 — `tls_checker.py` — remote TLS endpoint checks
**Accepted:** 2026-06-22 · commit `47d8301`

`checker/tls_checker.py` exports `check_tls(host, port, timeout) -> dict`
using stdlib `ssl`/`socket`. `expired.badssl.com` confirmed `severity == "expired"`
and `days_remaining ≤ 0` via live run. Error path (non-resolving host) returns
non-empty `error`, `None` days_remaining. Network tests marked
`@pytest.mark.network`.

---

## EW-002 — `severity.py` — threshold logic
**Accepted:** 2026-06-22 · commit `d300fac`

`checker/severity.py` exports `compute_severity(days_remaining: int) -> str`.
Returns exactly `"healthy"` / `"warning"` / `"critical"` / `"expired"`.
All eight boundary values covered by named test cases in
`tests/test_severity.py`. No external imports.

---

## EW-001 — Repo scaffolding
**Accepted:** 2026-06-22 · commit `6058aaf`

Repository baseline: `.gitignore` (excludes `.idea/`, `.venv/`, `results.db`,
`config/vault.yaml`, `config/local_*.yaml`, etc.), MIT `LICENSE` (Igal Vexler
2026), directory skeleton (`checker/`, `dashboard/`, `tests/`, `config/`,
`systemd/`), `requirements.txt` and `requirements-dev.txt` with pinned
versions, `config/targets.yaml.example` with `REPLACE_ME` placeholders only.
