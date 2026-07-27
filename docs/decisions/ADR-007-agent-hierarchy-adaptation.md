# ADR-007: Адаптация иерархии агентов (методология Сейсембаева)

- Статус: Accepted  
- Дата: 2026-07-27  
- Связано: ADR-001, ADR-003, ADR-004; [MARGULAN_APPLICABILITY.md](../architecture/MARGULAN_APPLICABILITY.md)

## Контекст

Получена спецификация многоагентной системы (L1 Master / L2 Directors / L3 Subagents) с принципами Context Isolation, Structured I/O, Human-in-the-Loop. Нужно внедрить полезное без ломки канона PH / Agents / Molt и без второго orchestration engine.

## Решение

1. **Принципы берём:** isolation, JSON handoffs, HITL.  
2. **Master Orchestrator не создаём как отдельный продукт:**  
   - классификация интента = `triage` (Agents governance);  
   - lifecycle Run = `Molt` (ADR-003).  
3. **L2 Directors = logical clusters над `routing.yaml` domains**, не новые сервисы:  
   - `STRATEGY` → PRODUCT_DEV (+ FIN/PS)  
   - `KNOWLEDGE` → DATA / memory (phase later)  
   - `MEDIA` → MEDIA_OPS  
   - `EFFICIENCY` → Personal_Helper only  
4. **L3 = pipeline steps + reviewers** (`STEP_PROFILES`, roundtable).  
5. **Cursor Agents / subagents** в IDE работают по тем же L3-ролям и JSON-контракту handoff; не подменяют Molt.  
6. **Стек:** оставляем CrewAI + rule_based; LangGraph/Neo4j/Qdrant — только по отдельному ADR после Phase C memory.

## Последствия

- Нужен `handoff.v1` schema и постепенная валидация.  
- В triage/meta появляется опциональное поле `agent_cluster`.  
- Документ Маргулана — источник паттернов, не SoT архитектуры MyWave.

## Rollback

Удалить/игнорировать `agent_cluster` и schema validation flag; pipeline остаётся на текущих list-payload handoffs.
