# Guarded project console release

Operations-only follow-up to PR #86. The application candidate remains source
898386aa1c1b766a3db088235163cf128dfa17ef and image
sha256:d5e33200cb8e5f66ea8ad93ed9d415d35f5c7f269dc08d6a3825bb0426dbe6e3.
No additional application code, dependency or migration change is included.

## Verified transport condition, 2026-10-23

Production nginx has the expected HTTPS vhost and forwards X-Forwarded-Proto;
it does not inject a fixed X-API-Key. FORWARDED_ALLOW_IPS is currently absent.
The container bridge gateway is 172.18.0.1. A release must explicitly trust only
the actual host-proxy gateway plus IPv4/IPv6 loopback. Wildcard/CIDR trust is
rejected. The deployment derives addresses from Docker metadata, not a broad
network range. An isolated full app.main rehearsal checks Secure cookies via the
host-proxy path and rejects forged forwarded-protocol headers from another peer.

## Operations pipeline

1. qualify_console_proxy.py --execute: synthetic data only, temporary internal
   Docker network, host-to-bridge requests without published ports, real app.main, positive proxy and
   negative untrusted-peer tests. Label-owned cleanup; no production restart.
2. project_console_release.py --public-base-url URL: preview current release plan.
3. Add --prepare: save current candidate profile and dedicated credential in a
   root-only directory, take a fresh custom-format PostgreSQL dump and restore
   it in a network-isolated temporary PostgreSQL. Verify migration 009 and full
   table fingerprints for projects, tasks, memory, workspaces and access grants.
4. Execute only with --prepared DIRECTORY and --owner-approved-plan HASH. The
   gate binds candidate image/source, operation code hash, current Compose hashes,
   transport evidence, exact proxy addresses, public destination and build time.
5. Recreate app only, no build/pull/dependency restart. Verify system health,
   source/schema, scoped auth and legacy missions, then a Secure public session,
   project discovery/read and logout. No production test task is created.
6. Any failed acceptance restores the previous exact 009 image/configuration,
   recreates app and verifies recovery. No downgrade or database restore occurs
   during rollback because this application release does not alter the schema.

Default mode does not apply configuration. Preparation performs backup and an
isolated restore; only explicit execution restarts production. The owner has
requested continued preparation; merge/deploy require the separate Owner Gate
specified in their original task. No approval hash is silently supplied by tools.
Credentials, database dumps, resolved Compose data and session cookies never enter
Git or public logs. A copied browser cookie remains a bearer token until its
15-minute expiry, dedicated-key rotation, or live permission revocation.

## Files and validation

- scripts/server/project_console_release.py: preview, restore-tested preparation,
  exact-plan approval, app-only cutover and rollback.
- scripts/qa/qualify_console_proxy.py: host proxy and untrusted-peer rehearsal.
- tests/isolated/test_console_release.py: configuration delta, trust boundaries,
  owner gate, exact recovery and distinct failed-recovery behavior.

Existing UI acceptance: Windows 117 isolated + 46 legacy checks; Docker 202 passed,
2 SQLite variants skipped with PostgreSQL variants executed. Warning categories
were DeprecationWarning, SADeprecationWarning, StarletteDeprecationWarning and
PytestConfigWarning; they are recorded as existing qualification limitations.
New operations tests and live transport/backup results will be recorded here.

The first transport rehearsal stopped because this Docker engine does not expose
a published-port binding on an internal network. Label-owned cleanup completed;
production was unchanged. The revised rehearsal reaches the private bridge IP
directly from the host, preserving the same trusted gateway source address and
the internal network without publishing ports. The failed run is not acceptance.
