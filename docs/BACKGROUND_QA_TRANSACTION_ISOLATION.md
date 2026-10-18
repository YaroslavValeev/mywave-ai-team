# Background runtime QA transaction isolation

The intermittent stop test used SQLite in-memory with StaticPool. The worker,
request handler and audit middleware opened separate SQLAlchemy sessions backed
by the same DBAPI connection. Closing a reader rolls back that connection's
transaction, including another session's uncommitted status update. This can
produce runtime cancelled with task NEW instead of REWORK.

A deterministic SQLAlchemy probe reproduced it: the shared-connection reader
observed uncommitted REWORK, then its close undid the writer update; the writer's
subsequent commit left NEW. A file database with separate connections kept the
reader at NEW until commit and persisted REWORK afterwards.

Only the background HTTP test module overrides db_session: a private temporary
SQLite file, NullPool and separate connections for workers and requests. It
restores repository globals through monkeypatch and resets the runtime before
disposing the engine. No production storage settings or task status logic change.
Production PostgreSQL already provides separate database transactions; this QA
change does not claim to prove every cancellation/worker failure mode there.

A regression test requires the reader not to see uncommitted changes and verifies
that closing it cannot undo the writer's committed task status. The actual HTTP
start/stop and Russian chat scenarios remain in the module without relaxed
assertions, increased timeouts or polling retries.

From the repository root: `python -m pytest tests/test_background_runtime.py -q`.
Docker QA uses the same test with a private writable /tmp; no live API, credentials
or network are needed. Rollback is reverting this QA-only change, without data
migration or production restart.
