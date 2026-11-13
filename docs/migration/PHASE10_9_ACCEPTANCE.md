# PHASE 10.9 — Domain-Aware Collaboration Flows and Handoff Intelligence

## Цель этапа

Собрать **domain-aware collaboration and handoff baseline**:
- collaboration model
- handoff patterns
- handoff readiness / blockage signals
- cross-role collaboration recommendations
- collaboration hotspots
- collaboration visibility в owner/project/role views

## Что считается завершённым

- [x] Collaboration model описана (COLLABORATION_MODEL_BASELINE.md)
- [x] Handoff heuristics описаны (HANDOFF_HEURISTICS.md)
- [x] Service layer есть (`app/services/collaboration_flows.py`)
- [x] Presenters есть (`app/presenters/collaboration_presenters.py`)
- [x] Project/role/portfolio views показывают collaboration signals
- [x] Web routes: `/owner/collaboration`, `/api/owner/collaboration`
- [x] Telegram commands: `/collaboration`, `/handoffs`, `/project_handoffs <key>`, `/role_collaboration <role>`
- [x] Playbooks и relation docs (COLLABORATION_FLOWS_PLAYBOOK.md, HANDOFF_PLAYBOOK.md, ROLE_DOMAIN_PROJECT_COLLABORATION_RELATION.md)
- [x] Recommendations учитывают collaboration signals (owner_recommendations.py)
- [x] Тесты покрывают основные сценарии

## Что остаётся следующим этапом

- Explanation assist
- Richer semi-automated tuning
- Agent-specific tuning workflows
- Domain-aware collaboration patterns refinement
- Optional collaboration action suggestions

## Entrypoints

| Тип        | Путь/Команда                         |
|-----------|--------------------------------------|
| Web       | /owner/collaboration                 |
| API       | GET /api/owner/collaboration         |
| Project   | /owner/project/{key} (блок Collaboration) |
| Portfolio | /owner/portfolio (блок Collaboration hotspots) |
| Dashboard | /owner (блок Collaboration hotspots) |
| Telegram  | /collaboration, /handoffs, /project_handoffs, /role_collaboration |

## Критерий готовности

Этап принят, если:
- collaboration model описана;
- handoff heuristics описаны;
- service layer есть;
- presenters есть;
- project/role/portfolio views показывают collaboration signals;
- web/Telegram entrypoints есть;
- playbooks и relation docs есть;
- recommendations учитывают collaboration signals;
- тесты проходят;
- ADR и acceptance docs созданы/обновлены.
