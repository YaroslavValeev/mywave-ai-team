# Isolated cold-start rehearsal

Run `scripts/verify_cold_start.py` against full immutable Docker image IDs.
Without `--execute` it only inspects the images. With `--execute` it creates a
unique Compose project with its own database volume and internal network.
It publishes no ports, mounts no host directories, reads no deployment `.env`,
generates temporary credentials and disables Telegram polling/notifications.

The rehearsal checks PostgreSQL health, successful Alembic migrations, then
application health and equality of the applied revision to the Alembic heads.
It repeats container creation three times: once with a fresh database, then
twice with the rehearsal database retained. A deliberately failed migration
must prevent application startup. Cleanup deletes only resources belonging
to the generated project; production containers and volumes are not selected.

The evidence JSON includes image IDs, each cycle, migration/health results,
the failed-migration gate and cleanup status. This verifies the rehearsal
topology, not deployment Compose, host reboot recovery or a real Telegram bot.
It must not be reported as proof of production polling uniqueness.

On the server, run from `/opt/mywave/ai-team` after obtaining this script:

```bash
APP_IMAGE="$(docker inspect --format '{{.Image}}' ai-team-app-1)"
PG_IMAGE="$(docker inspect --format '{{.Image}}' ai-team-postgres-1)"
python3 scripts/verify_cold_start.py --app-image "$APP_IMAGE" --postgres-image "$PG_IMAGE" --evidence /opt/mywave/ai-team-runtime/cold-start-evidence.json --execute
```

Use a new evidence filename for each run. If cleanup fails, inspect only the
exact generated project label recorded in evidence. Do not run global prune
or remove production volumes.
