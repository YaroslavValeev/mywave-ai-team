# Project console: implementation and release boundary

## Repository reconciliation (2026-10-22)

The restored F:/Проекты MyWave/NEW2026/AI-Team directory is the umbrella workspace,
not the GitHub Agents repository. Its branch feature/club-box-portable-mission has
17 unique commits versus 181 on the qualified Agents branch; most unique work is
portfolio/Club Box evidence. There is no origin remote on the umbrella repository.
Its existing services/agents_live junction resolves to C:/ProjectMyWave/MyWave_AI_TEAM_Presets_v1_1
at 0802c747e2f77428c86a4a20612840a9c1a638c4, older than the running b2a1182 release.
No umbrella history, nested checkout, junction or untracked credentials were merged
or replaced. Development now uses a separate Agents worktree on F: at
.codex-tmp/scoped-project-console, branch feature/scoped-project-console, based on
c9aa168 (PR #85). The umbrella and existing nested checkout remain intact.

## Browser capability

- /api/workspaces/console: Russian responsive shell, separate credential login.
- /api/workspaces/session POST: accepts dedicated key only via X-API-Key header.
- A signed HttpOnly, SameSite=Strict cookie lasts 15 minutes, scoped to /api/workspaces.
  HTTPS uses Secure; plain HTTP is rejected except loopback development hosts.
- No credential in URL, browser storage, response body or page source. The input
  is cleared after login. Each session is signed with the dedicated key; rotation
  invalidates old sessions. Logout clears this browser cookie; a copied cookie
  remains valid until expiry unless its key or permissions are revoked.
- /api/workspaces/projects filters active, unexpired membership AND product grant
  in SQL. Workspace ownership alone does not disclose other projects.
- Project selection loads only that project's tasks. Creation uses server-owned
  workspace/project IDs and the existing scoped transaction/audit. Reader roles
  can view tasks but cannot create. Writes via cookie require X-Workspace-Request: 1.
- Arbitrary text is rendered using textContent. CSP, no-store, no-referrer and
  nosniff apply. Wrong explicit credentials cannot fall back to a valid cookie.

## Acceptance and limits

Local focused tests initially passed 18 checks. Browser QA on a disposable SQLite
DB and synthetic credentials covered login, empty project, creation of NEW task,
safe literal HTML text, switching between two projects, reload and logout.
Responsive check: viewport client width 375, scroll width 375 (no horizontal overflow).
Screenshots remain outside tracked code under the umbrella .codex-tmp/scoped-console-evidence.
The complete isolated regression suite and Docker validation are recorded below
when complete; local Docker Desktop was initially unable to start, and VPS SSH
banner exchanges were intermittent. No production application was changed.

This does not start a scoped pipeline/executor, reclassify legacy mission 39,
prove portable Club Box delivery, or enable Telegram project selection.
The route is not deployed merely because local browser acceptance passed.

## Checks and rollback

From this Agents worktree, run:
python -m pytest tests/isolated --confcutdir=tests/isolated -q -p no:cacheprovider

Docker (requires working daemon, synthetic credentials only): build the repository
Dockerfile lite target, install pytest in a disposable QA image, then run the same
suite with networking disabled. PostgreSQL tests require an explicitly disposable
ai_team_workspace_qa_ database via WORKSPACE_TEST_DATABASE_URL.

Before rollout: review this PR and its base dependencies; qualify an immutable
image, verify proxy TLS handling and no credential header injection, check DB 009,
backup/restore and current grants, then obtain the release's Owner Gate approval.
No Compose change or migration is part of this application PR. Recovery is the
previous qualified 009 image/configuration, retaining data and dedicated key.
