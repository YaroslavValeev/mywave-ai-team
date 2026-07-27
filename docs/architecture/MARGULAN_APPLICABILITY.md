# Применимость архитектуры М. Сейсембаева к MyWave AI-TEAM

Статус: accepted baseline (анализ)  
Дата: 2026-07-27  
Источник: `ai_agent_architecture_margulan.md` (27.07.2026)  
Канон: [SYSTEM_CANON.md](SYSTEM_CANON.md)

---

## 1. Что обнаружено в документе Маргулана

Иерархия **L1 Master → L2 Директора-кластеры → L3 субагенты** с тремя принципами:

1. **Context Isolation** — узкий system prompt + только релевантная KB  
2. **Structured I/O** — обмен через JSON-протоколы  
3. **Human-in-the-Loop** — критичные действия только после approve владельца  

Кластеры L2: Стратегия/Инвестиции, Аналитика/Знания, Контент/Медиа, Личная эффективность.  
Стек в рекомендациях: LangGraph/AutoGen/CrewAI, Qdrant/Pinecone + Neo4j, OpenAPI на каждый L3.

---

## 2. Почему это важно для MyWave

У нас уже есть живой governance-контур (Telegram → triage → pipeline → roundtable → court → WAIT_OWNER), но:

- handoff часто «процессный» (шаблон), а не строгий JSON-контракт;  
- роли pipeline ≠ явные L2-директора (путаница «кто оркестратор»);  
- нет изоляции KB по субагентам;  
- документ Маргулана тянет **второй Master-оркестратор** — конфликт с каноном `Molt = orchestration owner`.

---

## 3. Решение: adapt, не replace

| Принцип / модуль Маргулана | Вердикт | Куда в MyWave |
|---|---|---|
| Context Isolation | **Берём** | Узкие `STEP_PROFILES` + scoped memory per role |
| Structured JSON I/O | **Берём** | Контракт handoff + валидация перед court |
| Human-in-the-Loop | **Уже есть** | `execute_gate` + Telegram approve; усилить список critical |
| Master Orchestrator (L1) | **Не дублируем** | = triage + Molt Run owner, не новый агент-продукт |
| L2 Директора | **Маппим на domains** | см. таблицу ниже |
| L3 субагенты | **Маппим на pipeline steps** | CONTENT, DATA, RC, FIN… |
| Qdrant + Neo4j сразу | **Откладываем** | Phase C; сейчас SoT + Sheets/SQLite |
| LangGraph как замена CrewAI | **Не сейчас** | CrewAI + rule fallback уже в проде |
| Директор личной эффективности | **PH later** | Personal_Helper, не Agents control-plane |

### Маппинг L2 → MyWave domains / owners

| L2 (Маргулан) | MyWave domain / слой | L3 ↔ pipeline / reviewers |
|---|---|---|
| Стратегия и Инвестиции | `PRODUCT_DEV` + FIN/PS | PS, FIN, RC, ARCH |
| Аналитика и Знания | `DATA` steps + future Memory/RAG | DATA, ML_PROMPT, RC (фактчек) |
| Контент и Медиа | `MEDIA_OPS` | CONTENT, PROMPT, BRAND, LEGAL |
| Личная эффективность | `Personal_Helper` (product) | triage inbox / calendar — вне Agents MVP |

### Маппинг оркестрации (критично)

```text
Маргулан Master          →  MyWave: triage (Agents) + Run lifecycle (Molt)
Маргулан L2 Director     →  domain cluster + route from routing.yaml
Маргулан L3 Subagent     →  pipeline step / CrewAI STEP_PROFILES / Cursor subagent
Маргулан Human approve   →  WAIT_OWNER + OWNER_APPROVAL_* gates
```

**Анти-паттерн:** второй Master поверх Molt или «директор» как UI-продукт в Agents.

---

## 4. Что переносим как есть (идеи)

- Изоляция контекста субагента  
- JSON-контракт между шагами  
- HITL на publish / money / PII / external send  
- «Адвокат дьявола» = RC / Risk Assessment  

## 5. Что рефакторим

- Формализовать handoff payload (schema)  
- Явно пометить L2-кластер в triage/meta  
- Owner-facing deliverable per cluster (как content draft для MEDIA_OPS)  
- Cursor Agent team: правила ролей = L3 профили  

## 6. Что откладываем

- Neo4j / полноценный RAG-граф  
- Отдельный продукт «Директор эффективности» в Agents  
- Замена CrewAI на LangGraph  
- OpenAPI на каждый L3 до стабилизации JSON handoff  

## 7. Риски

| Риск | Митигация |
|---|---|
| Два оркестратора | ADR-003 + ADR-007: Molt owns Run |
| Раздувание ролей | Только map на существующий `routing.yaml` |
| Prompt-only policy | Policy остаётся в yaml packages |
| Инвест-фокус документа ≠ MyWave wake/media | Кластер Strategy = product/finance MyWave, не VC-питчи |

## 8. Критерий готовности адаптации

- [x] Документ применимости + ADR  
- [ ] Handoff JSON schema в `packages/shared-schema`  
- [ ] `cluster` в triage meta (MEDIA / PRODUCT / KNOWLEDGE / OPS)  
- [ ] Cursor rules для agent team  
- [ ] Один smoke: MEDIA_OPS content_pipeline с валидным structured handoff  

Детальный rollout: [../migration/AGENT_TEAM_ROLLOUT.md](../migration/AGENT_TEAM_ROLLOUT.md).
