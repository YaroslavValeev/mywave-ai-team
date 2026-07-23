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

## Owner RU (после этого PR)

```bash
cd /opt/mywave/ai-team && set -a; source .env; set +a
git pull origin main
docker compose -f docker-compose.yml -f docker-compose.server-full.yml up -d --build
bash scripts/server_ops_check.sh
# секция molt → OK: не слушает 8765 (без --profile molt)
# с Molt: docker compose ... -f docker-compose.molt.yml --profile molt up -d --build
```
