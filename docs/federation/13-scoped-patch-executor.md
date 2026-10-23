# Scoped patch executor candidate

This adds a separate project-scoped path from a prepared UTF-8 Git patch to
isolated Python tests, a branch, commit and PR. It never calls the legacy runner,
global memory, gateway credential merger or legacy task API. It does not generate
patches from natural-language briefs. A prepared patch is input, not proof that
the business request has been implemented.

## Authority and lifecycle

Both active workspace membership and product grant are checked on every HTTP
request. Writers can prepare and queue patches. Approval/rework additionally
requires owner role in both records; project ownership labels grant no authority.
Browser writes retain the dedicated session and CSRF marker requirements.

`NEW/REWORK/EXECUTION_FAILED -> prepare -> WAIT_OWNER -> owner approval ->
EXECUTION_READY -> queue -> EXECUTING -> isolated tests -> branch/commit ->
push/PR -> APPROVED_WAIT_MERGE`.

The proposal binds task text digest/version, workspace/project, repository,
profile digest including its separate credential digest, base SHA, exact patch
digest and immutable validation image. Approval records that exact proposal.
Changed task/profile/key/source requires preparation and owner review again.
Rework increments the task version and rework count. The full proposed patch is
available for owner review as text, never rendered as HTML.

API paths under `/api/workspaces/{workspace_id}/projects/{project_id}`:

- `GET /execution/profiles`: registered profile IDs and repositories only.
- `GET /tasks/{task_id}/execution`: proposal, patch, run state and confirmed PR.
- `POST /tasks/{task_id}/execution/prepare`: `{profile_id, patch_text}`.
- `POST /tasks/{task_id}/execution/decision`: `{proposal_sha256, decision}`,
  where decision is `approve` or `rework`.
- `POST /tasks/{task_id}/execution/start`: `{proposal_sha256}`, returns 202.

The console exposes separate preparation, review and start actions. It does not
silently approve or start work after task creation. A PR is never marked DONE;
merge, deployment and business outcome validation remain separate owner gates.
This candidate does not add a scoped merge-confirmation or deployment endpoint.

## Separate trusted worker

The web application only persists the queue entry in existing Task/Run tables.
A database compare-and-set prevents duplicate claims across processes. Worker
selection filters registered scopes/profiles in SQL before its queue limit.
Before each phase it reacquires live writer access and the approving owner's
current membership/grant. Revocation, downgrade, rotation or changed inputs stop
the next phase. Permission writes serialize with in-flight phases; validation can
hold these locks for up to its bounded timeout.

The worker runs on a trusted Linux host in its own Python environment with Git,
GitHub CLI, SQLAlchemy, explicit database access and Docker CLI access. **Do not
mount the Docker socket into the web application.** Its bounded command, run in
that worker's source checkout with secrets supplied by its private service
environment, is `python -m app.workspaces.patch_worker --once`. No worker service,
timer, database credential, Docker mount or production profile is installed by
this application PR.

The persistent queue survives application restarts. A claimed job interrupted by
a host/worker crash is deliberately not replayed: it may already have committed
or pushed. Owner recovery must inspect the recorded run, clone lock, branch and
remote state before changing its status. This candidate has no automatic stale
job recovery or interactive cancellation. Failed validation leaves the real clone
unchanged; failures after a commit preserve that commit for owner inspection.

## Explicit configuration; default off

- `WORKSPACE_PATCH_EXECUTION_ENABLED=true` enables profile-backed API writes.
- `WORKSPACE_PATCH_WORKER_ENABLED=true` and an explicit `DATABASE_URL` are required
  by the worker. It never relies on the storage module's default connection.
- `WORKSPACE_PATCH_ROOTS_JSON` is the dedicated clone-root allowlist.
- `WORKSPACE_PATCH_PROFILES_JSON` is a JSON array of objects containing exactly
  `id`, integer `workspace_id` and `project_id`, absolute `workspace_path`,
  `repository` in owner/repo form, `validation_image` as a full `sha256:` ID,
  and `token_env` naming a `WORKSPACE_EXECUTION_TOKEN_*` secret.

App and worker must use the same profile/credential binding. The app needs only
read-only access to that separate clone at the same absolute path; the worker
needs write access. These future mounts belong to a separate infrastructure PR.
Production source, artifacts and legacy execution roots are rejected. Clones
cannot overlap across profiles, and credentials cannot be reused across scopes.
Shared owner, browser and global GH/GitHub credentials are rejected. Operators
must provision a separate repository-limited GitHub credential; no credential is
created, copied, displayed or rotated by this change.

The checkout must be clean, have the exact configured HTTPS origin and ordinary
local Git configuration. Unexpected filters, hooks, credential helpers, push URLs
and redirects in local Git configuration fail closed. Hooks and global/system Git
configuration are disabled for worker commands. Remote write permission and a
push dry run are checked before validation or source changes.

## Validation boundary

Only Git-tracked source plus the approved patch enter a disposable test tree.
Known credential files, symlinks and nonregular archive entries are rejected;
the patch scanner rejects known secret patterns and configured credential values.
This is a bounded check, not a guarantee that every possible secret is recognized.

The validation image must carry `mywave.scoped-validation=true`, contain no
credential environment variables, and be pinned by digest in the owner-reviewed
profile. It must be a trusted dependency image without other projects' runtime
data; the operator is responsible for image contents and dependency compatibility.

Tests run as UID/GID 65534 with network disabled, read-only root filesystem,
dropped capabilities, no-new-privileges, limited memory/CPU/PIDs and a temporary
directory. Only the disposable source tree is mounted; no Git metadata, project
token, production database, runtime configuration or Docker socket is supplied.
The command is fixed to `python -m pytest tests/ -q -p no:cacheprovider`; this first
profile supports Python/pytest projects only. Source files are checked for test
mutation. A timeout triggers removal of only the specifically labelled test
container. The real checkout is patched and committed only after tests pass.

The sandbox is a Docker process boundary on a trusted host, not a separate VM.
The trusted worker account can use Docker; untrusted project code cannot access
that account's environment or the daemon through this path. Raw subprocess output
and exceptions are never stored in task summaries, audit or HTTP errors.

## Qualification and rollback

Tests use disposable SQLite/PostgreSQL and real local Git. GitHub permission,
push and PR calls are stubbed to prevent live communications; those tests do not
prove a real scoped GitHub delivery. The host smoke additionally runs actual
Docker tests, proves failed tests prevent commit/publication, and checks that the
production container ID/image/health are unchanged. Qualification results are
recorded separately after execution.

No migration, dependency update, production restart or secret change is included.
Rollback: stop scheduling the dedicated worker, let an active bounded operation
finish and inspect its evidence, then disable the feature and restore the prior
application image. Preserve queue/approval/audit records and dirty clones. Never
reset a clone or replay a claimed run as part of an automatic rollback.

Before production activation: review this code and CI, qualify the chosen worker
topology/image, provision the dedicated project credential and clone, rehearse
recovery, and approve the concrete source/image/configuration release. A portable
Club Box and second-computer Windows acceptance remain separate work.

## Qualification recorded 2026-10-23

Executable source: `0acaeca4ade8fb40c346d8ede0fdf3099fdbc376`.
See `scoped-patch-qualification-20261023.json` for immutable images and evidence paths.

- Final isolated Docker qualification: **252 passed, 2 skipped** against SQLite
  and disposable PostgreSQL 15; real Uvicorn HTTP isolation/revocation/logout passed.
- Dedicated worker tests: **25 passed**; real Docker/Git host smoke passed,
  including failed validation blocking commit and publication. GitHub permission,
  push and PR calls were simulated; actual scoped external delivery is unverified.
- Desktop review verified prepare, owner approval, separate queue action,
  persistence after login, and clearing scoped patch/profile/result data on logout.
- Production remains source `898386aa1c1b766a3db088235163cf128dfa17ef`,
  migration `009`, health `ok`; task 38 `DONE`, task 39 `WAIT_OWNER`.
  The single-poller check and dedicated scoped access check passed.
- Production scoped execution remains disabled. No dedicated execution credential
  exists, and current workspace/project roles are `owner`/`writer`; approval
  requires `owner` in both. Do not silently elevate that grant or reuse a key.

The PR is a reviewable code candidate, not activation or business acceptance.
The stacked PR has no reported GitHub checks; isolated qualification does not
substitute for repository CI. Worker infrastructure, credential provisioning,
permission policy, live GitHub acceptance and an exact release Owner Gate remain
separate steps. No portable Windows Club Box or owner time savings are claimed.