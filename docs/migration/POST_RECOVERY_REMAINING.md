# Post-recovery remaining work

Snapshot: **2026-07-24** (Owner RU @ `e73fbec`+ ; Molt overlay live; stage-notify hardened)  
Prod: `agm.mywavewake.ru` health **ok**  
Agents `main`: sync after this PR

Связано: [INTEGRATION_THREE_LAYERS.md](INTEGRATION_THREE_LAYERS.md), [MOLT_ON_RU_CHECKLIST.md](MOLT_ON_RU_CHECKLIST.md)

---

## Closed (agents)

| Item | Status |
|------|--------|
| Post-recovery ops / CI / backups / URL hardening | **done** |
| RU Dashboard owner-facing + polish | **done** |
| Telegram stage-boundary notify + harden | **done** |
| `docker-compose.molt.yml` (`profiles: [molt]`, OFF by default) | **done** |
| ops-check asserts :8765 off when profile inactive | **done** |
| **Live** Molt `--profile molt` на RU (Owner GO) | **done** — см. [MOLT_ON_RU_CHECKLIST.md](MOLT_ON_RU_CHECKLIST.md) |
| Agents→Molt E2E на RU (bridge + auto_run task #16) | **done** (2026-07-24) |
| Ops parity (health `molt`, canonical backup, disk thresholds) | **planned** — upcoming PR |

---

## Owner PC optional

1. Visual PH: `run_ph_with_control.ps1`
2. BotFather / `CURSOR_API_KEY`

## Still deferred (policy)

1. Big-bang monorepo / dirty F: Agents — **не править**
2. Полный stream каждой реплики агента в TG
3. CrewAI без fallback
4. Авто-merge в `main`
5. LangGraph

## Owner RU (molt-first, после ops parity PR)

```bash
cd /opt/mywave/ai-team && set -a; source .env; set +a
git pull origin main
docker compose -f docker-compose.yml -f docker-compose.server-full.yml \
  -f docker-compose.molt.yml --profile molt up -d --build
bash scripts/server_ops_check.sh
# health API: checks.molt → ok/warn (governance stays up if molt down)
# backup cron: canonical_${DATE}.db alongside pg dump when molt_data volume exists
curl -sS -H "X-API-Key: $OWNER_API_KEY" http://127.0.0.1:8088/api/system/health | jq .checks.molt
```
