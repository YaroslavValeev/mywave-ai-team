# Pinned owner-operated runtime rollout

This is an operations PR based on the production source branch. It does not
merge application PRs, activate Club Box, change a booking writer or deploy itself.
The owner runs the reviewed wrapper in an idle maintenance window.

Application candidate: `20476d9fd5a8df89dd9ae33c1c61957569c39307`, image
`sha256:f85bdfc8aa43952d074521e295c312da97bda74ebc77435d6a2feece34415dc1`.
It contains the separately reviewed report/KPI/health/form-parser changes and
background QA isolation. It was built on the immutable production dependency
image, preserving the installed CrewAI version rather than upgrading dependencies.
The server's isolated full-dependency test run passed 377 tests with one Cursor
CLI skip. Real CrewAI kickoff with a deterministic local LLM passed separately;
that does not prove an external LLM or business pipeline outcome.

The actual running Compose profile is exactly:

- `/opt/mywave/ai-team/docker-compose.yml`;
- `/opt/mywave/ai-team/docker-compose.server-full.yml`;
- `/opt/mywave/ai-team-runtime/candidate.yml`.

The default Python release command only performs preflight. Execution additionally
requires `--execute --owner-approved-sha` matching the exact application commit.
It rejects a different base image, changed profile, environment drift, active
missions, mismatched test/image metadata or a backup/restore proof older than
24 hours. The verified dump is `recovery-20261018T075555734481Z.dump`.
The three Compose file digests are pinned to the inspected profile. Source-code
mounts that could override image identity are rejected; artifacts/execution
workspace mounts are retained. Repeating a successful rollout verifies the
already running image without recreating the app again.

Only image and APP release identity are updated in candidate.yml; other settings,
mounts, ports and allowed roots are retained. The app is recreated with no build,
pull or dependency restart. The helper backs up configuration/.env and application
artifacts privately before changing the app. Failure restores the previous
configuration and app and verifies its image/release. An unsuccessful rollback
is reported explicitly. No database migration is introduced.

The post-rollout gate requires Docker health, exact SHA/migration 007, full
system/Molt readiness, task 38 DONE, task 39 WAIT_OWNER, and truthful unverified KPI
fields. A failed gate never reports a successful release.

The separate recovery helper only permits mission 35 with its exact observed
creation timestamp, old IN_PIPELINE state, idle runtime and no active persisted
run. It changes only status/updated_at, keeps task content, and adds an audit
event atomically. It does not set DONE or claim a business result. Recovery is
idempotent in REWORK; unknown activity flags and all other identities/states are rejected. No HTTP request
is made while holding its task-row lock. The app rollback does not undo this
independent operational recovery.

For server SSH, working directory `/opt/mywave/ai-team`: fetch the reviewed
operations branch, extract run_owner_release_20261018.sh from its exact commit
into the private runtime directory, then invoke it with that operations SHA and
the exact application SHA. The wrapper uses an isolated directory derived from
the operations commit and aborts on every failed prerequisite. Do not submit new
missions during the short cutover; it rechecks idleness before recreating app.

Validation: isolated unit tests exercise restoration of both config files and
the previous app after failed readiness, explicit rollback failure, qualification
mismatches and missing owner gates. Recovery policy tests reject active/recent,
wrong-identity or completed work. Integration tests execute the actual recovery
worker against real SQLAlchemy models and verify both audit persistence and
transaction rollback if the audit insert fails. A server preflight must still
pass before use. Root credentials remain inside the running app, and are never
printed or passed to the test container.
