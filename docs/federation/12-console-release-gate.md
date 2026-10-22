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

The final release client rejects every HTTP redirect before forwarding keys or
cookies. A live loopback HTTP test proves that a redirect target receives no
request. Public acceptance verifies Secure, HttpOnly and SameSite attributes.
The Owner Gate additionally binds a digest of the effective environment; raw
resolved environment values are never logged or published. Any changed operation
code invalidates earlier preparation/approval hashes, requiring a fresh plan.

## Final verified preparation, 2026-10-23

Operations source: d5c546d1751b0880604f6afbc6f9cfa7d9ea1a5b.
Operation file SHA256: 7c9a7a129ac2dbb297e766b9a9d6766589320eb834d2b153b3489bbe29154164.
Local operations tests: 12 passed. Docker operations tests: 12 passed.
Real app.main transport rehearsal passed on an internal Docker network without
published ports: trusted host gateway produced a Secure/HttpOnly/SameSite cookie;
an untrusted peer forging HTTPS and non-loopback plain HTTP both received 400;
the shared owner key received 403. Production container unchanged, cleanup passed.
Proxy evidence: /opt/mywave/ai-team-runtime/console-proxy-qa-1wcg6935/qualification.json.

Final preparation: /opt/mywave/ai-team-runtime/console-release-qh0e_g4b.
Its fresh custom dump restored successfully in an isolated PostgreSQL; migration
009 and fingerprints of projects, tasks, memory, workspaces, memberships and grants
matched. Credential/config backups stay root-only on the VPS. Backup proof expires
24 hours after preparation; changed data/configuration requires fresh preparation.
The operation file, effective environment and current Compose files are bound to
the plan. Application data, dedicated key and schema remain unchanged.

Final plan SHA256:
cf43e4da9b4a99e75d9438945c9e62fa5543b8f30c9a7e1cbe83f6bdd24712ce.
Earlier plan 65fb11ffcfe8a1e00f11ee4300449121104484c73af30f62b12af6607bdbc8ba
was superseded by the redirect/environment protection and has no Owner approval.
No execution/merge/deploy was performed during preparation.

The proposed release uses qualified application source 898386aa1c1b766a3db088235163cf128dfa17ef,
image d5e33200cb8e5f66ea8ad93ed9d415d35f5c7f269dc08d6a3825bb0426dbe6e3,
production version 2026-10-23-898386aa1c1b, actual image build 2026-10-22T13:57:14Z,
and FORWARDED_ALLOW_IPS=127.0.0.1,::1,172.18.0.1.
Destination: https://agm.mywavewake.ru. Only app is recreated; this briefly
interrupts API and Telegram polling. No test mission is created in production.
The previous 009 image/configuration is retained for automatic recovery.

The owner subsequently approved the exact source, image and destination.
The installed operation used for the approved cutover is
/opt/mywave/ai-team-runtime/console-release-ops-d5c546d1751b/scripts/server/project_console_release.py.
Run it from /opt/mywave/ai-team with the approved plan and final preparation path;
preflight rechecks all live conditions before applying the configuration.
Do not execute with an earlier plan or silently bypass a failed preflight.

A final read-only nginx inspection succeeded: no X-API-Key, Authorization, Cookie
or Set-Cookie header variables were found in its log_format definitions. This
check did not print configuration contents or credentials and changed no service.


## Approved production release, 2026-10-23

The approved plan above executed successfully and returned
PROJECT_CONSOLE_RELEASE_PASSED. The operation verified the restored backup,
recreated only app, verified its exact image/source and migration 009, checked
scoped authorization, and exercised public HTTPS login, project discovery,
task reads and logout with a Secure/HttpOnly/SameSite session. No production
mission was created by acceptance, and no database migration was run.
Private execution evidence remains under the preparation directory as
outcome.json; secret/configuration backups and private logs are not in Git.

An independent request from Windows confirmed the public release source
898386aa1c1b766a3db088235163cf128dfa17ef, version
2026-10-23-898386aa1c1b, actual image build 2026-10-22T13:57:14Z and migration
009. The public console returned HTTP 200, a login form, a Content Security
Policy and Cache-Control: no-store, private.

The source PRs remain open: deployment approval did not authorize merging.
This release supplies scoped project/task viewing and task creation. It does
not prove scoped executor completion, delivery of the portable Club Box,
Windows second-computer acceptance, or owner time saved. Task 39 remains a
separate business mission; a working console does not complete that mission.


Additional post-release SSH connections timed out during banner exchange on four
bounded attempts. They did not execute the separate verification script and are
not claimed as independent server acceptance. The successful release operation
itself completed its health, authorization, mission and public-session checks;
independent Windows HTTPS checks passed afterward. No second cutover was run.
