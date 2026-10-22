# Dedicated owner credential and app-only API activation

Operations-only change for source b2a11824342f7b7921bcb3d84dcdc8913fa8e86b,
image ddb4d20a8dc980f81abb4033f0eba75eb24073250583d2d94313e78cdd77d3f1,
schema 009, workspace 1 and project 2. No application code or schema is changed.

## Credential boundary

The owner confirmed proceeding with a separate credential and tested activation.
Their later folder question concerned the local project copy and was withdrawn;
the project is not relocated. A private server-side credential location is still
required by this access design and is separate from the project distribution.

- Root-only directory: `/opt/mywave/ai-team-runtime/private/club-box`, mode 0700.
- Root-only `owner.env`, mode 0600; one random 64-character URL-safe value under
  WORKSPACE_KEY_CLUB_BOX_OWNER. Generated on the VPS, never supplied in argv/logs.
- Non-secret credential.json identifies owner:yaroslav, workspace 1, project 2.
- Only app receives that env_file; the common .env remains unchanged.
- Principal binding uses WORKSPACE_PRINCIPAL_BINDINGS_JSON and the env variable
  name, not the secret value. WORKSPACE_OWNER_PRINCIPAL_ID stays empty.
- The general owner key and existing dashboard cookie must receive 403 for
  scoped requests. They remain valid for their existing legacy operations.
- `status.py` reads the private file and checks localhost API access without
  displaying the credential or private task contents.

File permissions do not isolate a credential from root, Docker administrators
or the app process that needs it. This is not a sandbox against privileged code
or direct SQL. Sensitive/official mandates and scoped external executors remain
separate gates; this change does not enable them.

## Operator contract

`scripts/server/activate_club_box_owner.py` defaults to preview. --prepare only
generates or validates the credential; no app change. --execute requires the
exact owner-approved plan hash. The same release lock coordinates config edits.
Preflight requires the reviewed idle workspace bootstrap, restored backup younger
than 24 hours, exact Compose identity/hash/environment, expected mounts, health,
same image and bounded polling-container checks.

Plan SHA256: `b16464db3213341805d45c06d5be89db70a239bedae0099e0f5745bb779cc3e3`.

The script imports only low-level helpers from the checksum-pinned qualified
operations file under runtime/workspace-release-5dedabba4d17/scripts/server.
That dependency is the PR #83 helper at SHA256
`2eecbc646303badb2e611a3630276c2fec14ab7c8ae0461630d5789efdc41462`.
Its empty-scope preflight/readiness/recovery are deliberately not used.

Only runtime/candidate.yml is atomically changed: app env_file is appended,
scoped API enabled, one dedicated binding configured, shared-owner binding empty.
The helper never prints resolved Compose config because it contains the key.
App is recreated with --no-build --no-deps --pull never; image, ports, mounts,
database and other services are retained. A root-only activation directory saves
the previous profile, credential backup and metadata; never publish those files.

Acceptance checks dedicated/no/wrong/shared credentials, cross-scope denial,
overview access, legacy mission states, polling containers and credential absence
in every other running container. An exact already-active setup is verified
without another recreation. It does not rotate credentials automatically.

## Qualification and recovery

Local targeted tests: tests/isolated/test_owner_api_activation.py with confcutdir.
The server qualification harness uses a restored post-bootstrap backup, temporary
PostgreSQL and a real app process with synthetic credentials. It checks Compose
env_file behavior, observer service isolation, HTTP authorization, grant revocation
and a same-image switch back to disabled API. No production key is used in QA.
Temporary containers/networks and QA key files are removed by verified labels.

Failure restores the previous profile and restarts the same guarded 009 image
with API disabled. No old app, database restore or downgrade is attempted.
The private credential can remain protected for diagnosis; other services do not
inherit it. Database grants and existing mission data are not rewritten.

The initial QA v1 stopped on duplicated security_opt in its test-only Compose
merge; unit tests passed and production was unchanged. The QA override was then
reduced to the actual app delta. Do not treat the failed v1 as qualification.

## Scope of usability

Activation provides a dedicated HTTP API credential and a root-only local status
client. It does not add browser login, project selection in Telegram, scoped
orchestration, a portable Club Box package or a completed business mission.
Public proxy/browser access must be separately verified before claiming it.

## Verified qualification (2026-10-22)

Local Windows: 13 passed, 3 POSIX-only permission tests skipped. Docker Linux:
23 passed, including PostgreSQL/SQLite authorization and POSIX permissions.
Final isolated rehearsal: `/opt/mywave/ai-team-runtime/owner-auth-20261022-v3/qualification.json`.
Dedicated=200; absent/wrong/shared=403; cross-scope denied; revocation checked;
same-image disable rehearsed; observer secret absent; cleanup passed.
Production was unchanged during qualification. Black checks passed for all four
Python files. Canonical plan hash is identical on Windows and Linux.

## Production activation (2026-10-22)

The qualified v3 helper returned OWNER_API_ACTIVATED over SSH using the exact
plan hash. The image remained ddb4d20a8dc980f81abb4033f0eba75eb24073250583d2d94313e78cdd77d3f1.
Dedicated=200; absent/wrong/shared=403. Its acceptance also checked full health,
release identity, cross-scope denial, mission 38 DONE, mission 39 WAIT_OWNER,
other-container credential absence and polling-instance ownership.
The shared owner key is not bound. Private credentials and the previous profile
are retained only on the server; the common .env was not edited.

An independent public health request after activation returned ok, source
b2a11824342f7b7921bcb3d84dcdc8913fa8e86b and migration 009. This public health
request does not establish public scoped authentication or browser usability.

## Owner-run client confirmation (2026-10-22)

The owner supplied the result of executing the installed status.py client in
an SSH session on the production server, from /opt/mywave/ai-team:

```json
{
  "access_verified": true,
  "workspace_id": 1,
  "project_id": 2,
  "task_count": 0
}
```

This closes the outstanding independent installed-client check. It is owner-run
evidence supplied in the conversation, not another remote probe by this agent.
Zero tasks means no tasks are currently returned in the scoped Club Box project;
it does not establish completion of Club Box or relocate legacy mission 39.
The earlier SSH timeouts remain historical and do not invalidate this later check.
No app restart, key rotation, grants update or database migration is needed.
PR can leave draft for review; merge and further deployment remain separate gates.
