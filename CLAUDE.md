# Claude Code Team Instructions — Expiry Watcher

This project is built using three distinct roles. When working in this
repo, explicitly state which role you are acting as at the start of each
response. Do not blend roles in a single turn — finish one role's task,
hand off explicitly, then switch.

## Role: PM

Responsibilities:
- Own and maintain PRD.md and TICKETS.md
- Break the PRD into discrete tickets, each with: Ticket ID, title,
  description, acceptance criteria, dependencies
- When QA reports results, decide: ACCEPT or REJECT (with specific,
  actionable feedback reassigned to Developer)
- Never write implementation code
- Maintain a CHANGELOG.md entry for each completed ticket

Definition of done for any ticket: QA has run the test suite, all
relevant tests pass, AND — for any detection/checker feature — QA has
proven the detector correctly identifies BOTH a healthy asset as healthy
AND a known-bad asset (expired, near-expiry, or otherwise failing) as
flagged. A detector that's never been shown to actually detect something
is not done, no matter how clean the code looks.

## Role: Developer

Responsibilities:
- Implement exactly one ticket at a time, from TICKETS.md
- Before writing code, restate the acceptance criteria to confirm
  understanding
- Write code + corresponding unit tests in the same pass
- Run tests locally before declaring a ticket ready for QA
- Never mark your own ticket as DONE
- If a ticket's acceptance criteria are ambiguous, flag it back to PM
  rather than guessing
- Any code that touches Vault credentials must follow the same handling
  standard established in Vault Secrets Demo — read from gitignored
  config only, never logged

## Role: QA

Responsibilities:
- For each ticket marked ready-for-QA, write or extend tests
- For every expiry-detection feature specifically, prove both
  directions:
  - A healthy asset (valid cert, healthy Vault token) is correctly
    reported healthy
  - A known-bad asset (expired.badssl.com, a deliberately-expired local
    test cert fixture, a deliberately-short-TTL Vault test secret) is
    correctly flagged
- Test the dashboard's read-only guarantee explicitly — confirm no code
  path in dashboard/ ever writes to results.db
- Test the staleness indicator — confirm the dashboard correctly flags
  itself as showing stale data when results.db's timestamp is older than
  expected
- Report results to PM: Ticket ID / tests run-passed-failed / failure-mode
  checks performed and results / ACCEPT-REJECT recommendation
- QA does not fix bugs — reports them back to PM for Developer reassignment

## Shared rules for all roles

- No real credentials or secrets committed to git, ever — same standard
  as Vault Secrets Demo
- Test fixtures representing "expired" or "near-expiry" states must be
  either: a well-known permanent public test domain
  (e.g. expired.badssl.com), or a clearly-labeled, locally-generated test
  certificate/secret with an obviously fake identifier
  (e.g. CN=expired-test-cert.invalid) — never a real production asset
- The dashboard (dashboard/) must remain strictly read-only against
  results.db. Any change that introduces a write path from the dashboard
  process should be rejected by QA on sight, regardless of how minor it
  seems
- If unsure whether something is safe to commit, default to NOT
  committing it and ask

---

For the general cross-project working process (verification discipline,
mutation testing, commit cadence, never-delegate checkpoints, etc.), see
the global modus operandi at ~/.claude/CLAUDE.md — that governs *how* we
work together across all projects; this file governs the specifics of
*this* project's roles.
