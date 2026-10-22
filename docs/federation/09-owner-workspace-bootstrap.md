# First owner workspace: explicit bootstrap

This operator-only script creates one empty workspace and one empty project.
It is not an agent tool, HTTP endpoint, authentication binding, Federation
mandate or permission to run external actions. Application image is unchanged.

## Reviewable plan

| Field | Value |
|---|---|
| Qualified app source | b2a11824342f7b7921bcb3d84dcdc8913fa8e86b |
| Required schema | 009 |
| Logical principal | owner:yaroslav |
| Workspace | slug mywave, name MYWAVE, kind MYWAVE |
| Project | slug mywave-club-box, name Club Box, type product, stage build |
| Membership | owner, this workspace only |
| Product grant | writer, this project only |
| Existing records / mission 39 | untouched |
| HTTP intake / key bindings / Telegram scope / external execution | not enabled |

The logical principal is a new internal identifier, not an inferred Telegram
user ID or proof of an official role. A future, separately approved authentication
binding must connect a real owner credential to it before scoped HTTP access.
Use a separate owner credential and an app-only secret source at that gate:
the existing general owner credential is also used by internal integrations.
Do not implicitly bind this principal to shared OWNER_API_KEY or put its new
secret into a common env file inherited by Molt/other services.
Project writer permits the registered internal read/write operations; it does
not register any executor, permit merge/deploy or create an official mandate.

Plan SHA256: `c2d172816504e9376709ea084b2407543e1d91c305b8638056280e7d0f2b917c`.
Code changes that change the plan invalidate the previous approval hash.

## Execution contract

`scripts/server/bootstrap_mywave_club_box.py` defaults to SELECT-only preview.
It runs inside the exact qualified app container via stdin, using a standard
administrative SQLAlchemy Session; using LegacySession here would deliberately
deny scoped writes. The script is not installed in the app or exposed to LLMs.
Never use the privileged session pattern in user-facing request handlers.

Execution requires `--execute --owner-approved-plan` and the exact hash above.
Runtime must match source/schema, scoped API must be disabled, authentication
bindings empty, and runs/missions idle. Workspace/project conflicts, partial
setups, changed/revoked/expired roles and unexpected extra permissions deny
without overwriting anything. It does not seed a generic/default project or
infer the classification of existing MyWave/Federation data.

All four records plus an approval audit are flushed/committed atomically.
PostgreSQL advisory locking coordinates simultaneous copies of this bootstrap;
database uniqueness also applies. It does not coordinate arbitrary admin SQL.
An exact existing setup returns unchanged and does not duplicate the audit.

## Validation and evidence

Local PowerShell, repository directory:

```powershell
python -m pytest tests/isolated/test_owner_workspace_bootstrap.py --confcutdir=tests/isolated -q -p no:cacheprovider
```

`scripts/server/qualify_owner_workspace_bootstrap.py` runs only on the VPS as
root from a private staging folder containing the script and test. Its only
production DB operation before the final SELECT-only preview is a read-only
pg_dump. The fresh 009 backup is restored in a network-disabled, memory-limited
temporary PostgreSQL. Preview/apply/repeat are tested on that restored copy;
legacy project/task/memory fingerprints must remain unchanged. Approval is
supplied only inside the isolated copy, never to the live production preview.
Additional SQLite/PostgreSQL tests cover transaction failure, collisions,
permission revocation, changed plan, legacy filtering and concurrent operators.
Private backup/logs must remain on the server; publish sanitized summary only.

### Qualified on 22 October 2026

- Local: 19 passed, 1 PostgreSQL-only case skipped.
- Docker SQLite: 19 passed, 1 PostgreSQL-only case skipped.
- Docker PostgreSQL: 20 passed, including simultaneous operators.
- Fresh production 009 dump restored successfully; tasks 38 DONE and 39 WAIT_OWNER.
- Actual CLI preview/apply/repeat on the restored copy passed; exactly one audit;
  legacy project/task/memory fingerprints preserved.
- Live production preview passed SELECT-only; no production grants created.
- Isolated resources cleaned up; no production app restart/image/env change.
- Staging: `/opt/mywave/ai-team-runtime/owner-bootstrap-20261022-v1`.
- Script SHA256: `1ac5beb51f375e021a9d66eace4dc3346a69816e99355ce7187c6529ce228c2c`.
- Fresh backup: `production-009.dump` in that directory; SHA256
  `2ebf4fd9d0be88b5fa63cc98fadde8ea776b9b173b202a857ec2f3b7d030acb9`.
- Full private proof: `qualification.json` in that directory.

The next owner step is checksum/image/backup-age verification followed by
the exact approved-plan execution. Do not enable WORKSPACE_ACCESS_ENABLED yet.

## Recovery and next gate

Failure before transaction commit rolls everything back. After a successful
commit the empty setup is safe to leave with the API disabled; repeated runs
do not add permissions. No automated delete/downgrade/old-DB restore is provided.
Removal requires an explicit review of dependent data and approvals. Retain
production access guards; never return to an old app that ignores workspace_id.

Bootstrap success does not enable task execution, populate a knowledge base,
prove Club Box delivery or connect Telegram to the new scope. Authentication
binding and API activation need a separate, tested operations change; scoped
registry/action policies and Telegram routing are subsequent application work.
