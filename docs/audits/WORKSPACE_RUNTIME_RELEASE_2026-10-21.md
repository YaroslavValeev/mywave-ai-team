# Workspace runtime release gate, 2026-10-21

This is an infrastructure-only, owner-operated release helper. It does not
enable workspaces, create grants, classify existing data or execute missions.
Application code and qualified source remain in the separate integration PR.

## Reviewed inputs

- Current source: `20476d9fd5a8df89dd9ae33c1c61957569c39307`, migration 007.
- Current image: `sha256:f85bdfc8aa43952d074521e295c312da97bda74ebc77435d6a2feece34415dc1`.
- Target source: `b2a11824342f7b7921bcb3d84dcdc8913fa8e86b`, migration 009.
- Target image: `sha256:ddb4d20a8dc980f81abb4033f0eba75eb24073250583d2d94313e78cdd77d3f1`.
- Actual Compose: production docker-compose.yml + server-full + runtime/candidate.yml.
- Fresh backup: `backups/pre-workspace-20261021T200411Z-9Iq8Nj` under runtime.
- Owner-run restoration verified 007, task 38 DONE and its merge SHA.
- Owner-run migration rehearsal: `migration-check-Vcs9K0/result.txt`, upgraded
  a restored real backup to 009; project/task/memory fingerprints unchanged;
  workspaces, memberships, grants and classified records all empty.
- Config/artifact backup: `backups/release-files-20261021T201458Z-5Yb10V`.
  Its configuration archive contains secrets; never publish it.

## Preconditions and behavior

Default invocation only checks the exact production identity, mounts, Compose
hashes/environment, qualification, fresh restore/rehearsal proofs, file hashes,
persisted and in-process mission idleness, full health and same-token Docker
containers. It does not recreate containers or write production configuration.
A local release lock is created; it coordinates this helper, not arbitrary
external writers or other servers. Docker inspection does not prove cross-host
Telegram polling exclusivity.

The live Molt HTTP container inherits the same token through its env file.
It is not classified as a poller only when its exact reviewed image
`690836b01c6fbce306d2ada4cbce4bbd3bcd63c4971007d27b48896fc9f92467`,
HTTP-only uvicorn command, absent entrypoint, disabled/unset polling flag and
sole /data volume all match. An unknown image/command, code mount or enabled
polling loses that exemption and blocks release. Molt is not stopped or changed.

Execution requires `--execute --owner-approved-sha` with the exact target source.
Keep the maintenance window free of new owner/bot tasks and administrator writes.
The helper stops the old app, rechecks DB idleness, archives frozen artifacts,
and changes only runtime/candidate.yml. It preserves image build metadata,
sets production environment, disables workspace intake and clears principal
bindings. Compose runs only app, with no build, pull or dependency restart.
It checks 009, full health, legacy fingerprints, missions 38/39 and Docker pollers.
No database restore, downgrade, membership seeding or business action is automated.

## Recovery boundary

If failure occurs while the database is still exactly the empty, unclassified
007 baseline, the helper restores the old profile and verifies the old app.
After 008/009 appears, the old image cannot resolve that Alembic revision.
The helper therefore stops the app and leaves maintenance recovery evidence;
it does not pretend the old startup command is a safe rollback. Repair forward
with guards retained. Do not restore an old DB automatically, bypass migrations,
enable scoped intake, or remove access guards as an incident workaround.

This fail-closed behavior can cause downtime after a post-migration failure.
Successful preflight is not owner approval or a successful production release.

## Validation

Local PowerShell, this checkout directory:

```powershell
python -m pytest tests/isolated/test_workspace_runtime_release.py tests/isolated/test_owner_runtime_release.py --confcutdir=tests/isolated -q -p no:cacheprovider
```

Tests cover schema/activity gates, exact owner approval, stale proofs, changed
backups, mount injection, competing Docker tokens, disabled-intake configuration
and fail-closed recovery after migration. Run the same tests in a disposable
network-disabled candidate container with a read-only qualification mount.
No app regression rerun is implied: this PR changes operations scripts only.
The existing GitHub workflow targets main; stacked PRs do not imply GitHub CI.

The next owner command is default preflight only. A deployment command must
identify this exact helper revision and its SHA256 after preflight succeeds.

## Completed qualification

- Local isolated tests: 34 passed.
- Disposable candidate Docker container: the same 34 passed; network disabled,
  read-only root and qualification mount, 384 MiB memory cap, no production env.
- Server default preflight: passed, app_changed=false, active_missions=0,
  backup_restore=passed, migration_rehearsal=passed, target_migration=009,
  workspace_api_enabled=false. No rollout was executed.
- Qualified helper revision: `5dedabba4d17`.
- Server staging: `/opt/mywave/ai-team-runtime/workspace-release-5dedabba4d17`.
- Helper SHA256: `2eecbc646303badb2e611a3630276c2fec14ab7c8ae0461630d5789efdc41462`.
- The earlier staging directory `workspace-release-3f4fdf2` is marked superseded;
  it blocked on inherited Molt credentials and never changed the app.

The preflight prerequisite above is now satisfied. The owner can invoke the
qualified helper with the exact source approval to open the maintenance window.
Production success remains unproven until that command returns the verified
release outcome and an independent runtime check confirms it.
