# PRD — Expiry Watcher

A small, cron-driven monitoring tool that detects certificates, keys, and
credentials approaching expiry across multiple sources — TLS endpoints,
HashiCorp Vault, and the local filesystem — and presents results via a
read-only status dashboard. Built as a companion to, and consumer of,
Vault Secrets Demo.

## Problem statement

Expiring certificates and credentials are a classic silent-failure
category: the asset works perfectly right up until the moment it doesn't,
with no warning in between unless someone is actively checking. A single
missed TLS renewal or an unnoticed Vault AppRole `secret_id` TTL can take
down a service with zero advance notice. This project demonstrates a
small, honest monitoring pattern for catching these before they become
outages — built using a real, valuable architectural pattern (the
checker and the dashboard are separate processes, so a failure in one
doesn't hide a failure in the other) rather than a single fragile script
that does everything.

## Goals

- G1: Detect TLS certificates approaching or past expiry, for both
  remote endpoints and local certificate files on disk
- G2: Detect Vault AppRole and token TTLs approaching expiry, against a
  real running Vault instance (the existing Vault Secrets Demo project)
- G3: Persist check results with a timestamp, so staleness of the data
  itself is visible and honest — not just staleness of the monitored
  assets
- G4: Serve a read-only status dashboard, architecturally separate from
  the checking process, so a dashboard crash doesn't stop checks and a
  checker crash doesn't take down the dashboard
- G5: Prove the alerting actually triggers correctly — not just that it
  runs without error — using known-bad test fixtures (expired.badssl.com,
  a deliberately-expired local test cert, a deliberately-short Vault TTL)
- G6: Zero secrets or credentials committed to git, same standard as
  Vault Secrets Demo

## Non-goals (v1)

- AWS IAM key age checking — explicitly deferred to a stretch ticket,
  same treatment as Azure/GCP in the Vault project
- OAuth refresh token expiry — excluded entirely; no clean generic check
  mechanism, low payoff for the complexity
- Push notifications (email, Slack, etc.) — v1 is dashboard-only; an
  alerting-channel integration is a natural v2 addition, not core scope
- Historical trend graphs — the dashboard shows current state with a
  "last checked" timestamp, not a time-series chart. SQLite stores
  history from day one (so this is buildable later), but rendering it
  is out of scope for v1

## Success criteria

- A fresh clone + a single setup script gets the checker and dashboard
  running against real test data in under 5 minutes
- The checker correctly identifies: a healthy cert, an expired cert
  (via expired.badssl.com), a healthy local cert file, a deliberately
  expired local cert file, a healthy Vault secret, and a deliberately
  near-expiry Vault secret — six known states, six correct results
- The dashboard correctly displays all six, color-coded by severity
  (healthy / warning / expired), and correctly shows "last checked: stale"
  if the checker hasn't run recently
- Full test suite, including mutation tests proving the expiry-detection
  logic actually catches a real expired/expiring asset, not just a
  syntactically-valid one
- README documents the architecture honestly, including what's tested
  (Linux, real domains, real Vault) and what's stretch/untested (AWS)

## Architecture summary

```
systemd timer / cron
  └── check.py (Python)
        ├── checks TLS endpoints (ssl + socket, stdlib)
        ├── checks local cert files on disk (cryptography library)
        ├── checks Vault AppRole/token TTLs (hvac, reusing Vault
        │     Secrets Demo's existing AppRole pattern)
        └── writes results + timestamp to SQLite

FastAPI app (dashboard.py)
  └── READ-ONLY — queries the same SQLite file, never writes
        ├── GET /status — JSON, all monitored items + severity
        └── GET / — simple HTML table view, color-coded
```

The separation between `check.py` (writer) and `dashboard.py` (reader)
is deliberate — see Design decisions below.

## Design decisions and rationale

| Decision | Reasoning |
|---|---|
| Cron/timer-driven checker, separate from the dashboard | If the dashboard process crashes, checks keep running. If the checker breaks, the dashboard can still show the last-known state honestly, with a visible staleness indicator — better than either coupling them or losing history on a dashboard restart |
| SQLite for results | Enables a real "last checked" timestamp and future history/trending, not just current state; consistent with the pattern already used in Study Hub |
| Dashboard is strictly read-only | Prevents a whole category of bugs (dashboard accidentally corrupting check state) and keeps the architecture honest about which process is the source of truth |
| Reuses the existing Vault Secrets Demo instance and AppRole pattern | Avoids redundant infrastructure, ties the two projects together as a coherent body of work, reuses an already-tested auth pattern |
| Known-bad test fixtures (expired.badssl.com, deliberately expired local cert, deliberately short Vault TTL) | Same principle as the Vault project's mutation testing — an expiry detector that's never actually detected an expiry is unverified, not proven |
| AWS IAM key age deferred to stretch ticket | Keeps v1 scope to checks that can be fully tested today without new cloud credentials; avoids the "13 check types, none well-tested" scope-creep trap |

## Open questions / decisions still needed

- Exact severity thresholds (e.g. "warning" at 30 days, "critical" at 7
  days) — default proposed, adjustable via config
- Whether `check.py` runs via systemd timer (consistent with your
  existing IL Job Scraper pattern) or plain cron — leaning systemd timer
  for consistency with your other local automation
