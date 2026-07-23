# Post-recovery remaining work

Snapshot: **2026-07-23** (Owner RU @ `e73fbec`+ ; Molt overlay draft; stage-notify hardened)  
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
| `docker-compose.molt.yml` (`profiles: [molt]`, OFF) | **done** (live = Owner GO) |
| ops-check asserts :8765 off | **done** |

---

## Owner PC optional

1. Visual PH: `run_ph_with_control.ps1`
2. BotFather / `CURSOR_API_KEY`

## Still deferred (policy)

1. Big-bang monorepo / dirty F: Agents — **не править**
2. **Live** Molt `--profile molt` на RU — только после явного GO
3. Полный stream каждой реплики агента в TG
4. CrewAI без fallback
5. Авто-merge в `main`
6. LangGraph

## Owner RU (после этого PR)

```bash
cd /opt/mywave/ai-team && set -a; source .env; set +a
git pull origin main
docker compose -f docker-compose.yml -f docker-compose.server-full.yml up -d --build
bash scripts/server_ops_check.sh
# секция molt → OK: не слушает 8765
```
