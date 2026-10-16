# Health readiness callback starvation

The server probe established that Molt calls app's lightweight /health and that
the endpoint responds directly. However, /api/system/health called synchronous
DB/network probes from an async handler. While app waited for Molt /ready, Molt's
callback to app could not be processed on that same blocked event loop.

The API and the two dashboard handlers that collect system health now offload
the collector with asyncio.to_thread. The lightweight liveness route and auth
are unchanged. Thread context is propagated by to_thread; health queries create
their own database sessions. No polling, secrets, deployment or schema changes.

The regression test executes the actual system router through ASGI and requires
a concurrent liveness callback to succeed while the collector waits. It fails
on production's previous source and passes with the offload. Existing Molt
health checks additionally preserve readiness/error semantics.

Before rollout: build a pinned release, verify active runs and restore-ready
backup, preserve the current candidate configuration and rollback image, and
obtain the explicit Owner Gate for deployment. After rollout, check system health
and Molt ready together and repeat parallel liveness/readiness checks. Other
unrelated causes of readiness failure must still be diagnosed independently.
Rollback is restoring the previous application image; no record migration.
