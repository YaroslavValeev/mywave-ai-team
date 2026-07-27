# AGENT TEAM ROLLOUT — план для AI-агентов и субагентов

Статус: active  
Дата: 2026-07-27  
Основание: ADR-007, [MARGULAN_APPLICABILITY.md](../architecture/MARGULAN_APPLICABILITY.md)

---

## Цель

Внедрить лучшие практики из архитектуры Маргулана **поверх** существующего AI-TEAM, без второго Master-оркестратора и без big-bang.

---

## Роли команды (как работаем в Cursor + на RU)

### L1 — Orchestration (не «ещё один чат-бот»)

| Роль | Кто | Задача |
|---|---|---|
| **Router / Triage** | Agents `run_triage` + CrewAI triage | domain, task_type, criticality, plan/execute, gate, `agent_cluster` |
| **Run Owner** | Molt | lifecycle Run, execution events |
| **Lead Integrator** | Cursor parent agent (этот чат / TPM) | план, ADR, merge-ready PR, команды Owner |

### L2 — Cluster leads (логические директора)

| Cluster | Lead (логический) | Когда активируется |
|---|---|---|
| MEDIA | CONTENT→BRAND pipeline | `MEDIA_OPS` |
| STRATEGY | PS→FIN/ARCH | `PRODUCT_DEV`, money/impact |
| KNOWLEDGE | DATA→RC | evidence, ParserNews, KB |
| EFFICIENCY | Personal_Helper | вне Agents MVP |

### L3 — Субагенты (исполнители)

| Субагент | MyWave step | Cursor subagent_type (IDE) | Deliverable |
|---|---|---|---|
| Content draft / ToV | CONTENT, BRAND | generalPurpose / explore | message draft, tone check |
| Prompt shape | PROMPT / ML_PROMPT | generalPurpose | CTA, channels |
| Data / contacts | DATA | explore + shell | COUNT/export checklist, CSV later |
| Risk / Devil | RC, LEGAL, SEC | bugbot / security-review / explore | risk_table |
| Architect bounds | ARCH | explore | PLAN vs EXECUTE boundaries |
| Shell / ops | DEVOPS | shell | RU commands, compose |
| Code implementer | FE_BE / parent | parent agent | PR, tests |
| Docs synthesizer | COURT / parent | parent | verdict, rollout docs |

### Human-in-the-Loop (Owner)

- Telegram: approve / rework / clarify / LLM tier  
- Critical: publish, mass outreach, git push, PII export, money  

---

## Пошаговый план (вся команда)

### Phase 0 — Align (1 день) ✅ / сейчас

1. Зафиксировать применимость + ADR-007.  
2. Cursor rule: иерархия и запрет второго оркестратора.  
3. Schema draft `handoff.v1`.  
**Rollback:** удалить docs/rule, код не затронут.  
**Owner:** merge PR docs.  
**Auto:** Cursor agents пишут docs/schema.  
**Manual:** Owner читает ADR-007.

### Phase 1 — Structured handoff (2–4 дня)

1. Добавить JSON Schema / yaml в `packages/shared-schema/handoff_v1.yaml`.  
2. Rule-based pipeline заполняет обязательные поля: `summary`, `decisions`, `artifacts`, `next_action`, `deliverable` (если MEDIA).  
3. Court читает `deliverable` в первую очередь (уже частично для content).  
4. Тесты: content_pipeline + generic feature.  
**Rollback:** feature flag `HANDOFF_V1_VALIDATE=false`.  
**Deps:** Phase 0.  
**Compat:** старые list handoffs остаются.  
**Auto:** implement + pytest.  
**Manual:** Owner smoke #TASK MEDIA на RU.

### Phase 2 — agent_cluster in triage (1–2 дня)

1. Маппинг domain → cluster в triage meta.  
2. Telegram summary показывает кластер простым языком.  
3. Не менять routing.yaml routes без нужды.  
**Rollback:** игнор поля cluster.  
**Owner:** visual check TG.

### Phase 3 — Context isolation packs (3–5 дней)

1. На шаг передавать только: owner_brief excerpt + prior deliverable + policy snippet (не весь history dump).  
2. CrewAI step prompt: запрет «универсального» агента.  
3. Для MEDIA уже есть `content_intent` — образец для STRATEGY (fin brief) / KNOWLEDGE (evidence pack).  
**Rollback:** вернуть полный brief.  
**Manual:** сравнить длину handoff до/после.

### Phase 4 — Cursor Agent Team playbook (непрерывно)

При каждой крупной миссии Owner/Lead:

1. Parent = Lead Integrator.  
2. Параллельно: `explore` (код/ParserNews), `shell` (RU cmds), `generalPurpose` (drafts).  
3. Security/bugbot — только на PR с кодом.  
4. Итог всегда: SoT task + artifact + Owner commands.  
**Не делать:** субагент «Master» который invents policy.

### Phase 5 — Knowledge L3 light (later)

1. ParserNews COUNT/export tool (уже доказан Sheets path).  
2. MemoryEntry в shared-core без Neo4j.  
3. Factcheck = RC + источники в artifact.  
**Отложено:** Qdrant/Neo4j.

### Phase 6 — Efficiency cluster

Только через Personal_Helper product layer — не в Agents repo.

---

## Критерии готовности Phase 1 (первый внедряемый срез)

- Schema `handoff.v1` в репо  
- Cursor rule активен  
- Тесты зелёные  
- На RU: новая MEDIA задача показывает structured deliverable (как #30) + cluster label (после Phase 2)

---

## Команды Owner на RU (после merge PR этого пакета)

```bash
cd /opt/mywave/ai-team
```

```bash
set -a && source .env && set +a
```

```bash
git fetch origin && git checkout main && git pull origin main
```

```bash
docker compose -f docker-compose.yml -f docker-compose.server-full.yml -f docker-compose.molt.yml -f docker-compose.ollama.yml up -d --build app
```

Smoke: новый `#TASK` в MEDIA_OPS; дождаться WAIT_OWNER; смотреть full report.
