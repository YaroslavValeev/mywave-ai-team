# Bridge: MyWave Presets ↔ agency-agents (pool ~51)

Цель: использовать модель “большого пула” (как в agency-agents), но управлять им
через **теги навыков** + **правила несовместимости** + **выделенные пресеты конвейеров**.

## 1) Как мыслить о 51 агенте
Вместо попытки держать “жёсткий список имён”, AGM использует:
- **skill tags**: `dev.backend`, `dev.frontend`, `devops`, `security`, `legal`, `finance`, `product`, `ux`, `brand`, `content`, `ml.cv`, `data`, `qa`, `research`, `event_ops`
- **stage tags**: `pipeline_only`, `roundtable_only`, `either`
- **risk tags**: `pii_sensitive`, `prod_changes`, `publications`, `money_contracts`
- **domain tags**: `product_dev`, `media_ops`, `events`, `game`, `infra`, `sponsor_platform`, `rnd_extreme`

AGM выбирает 3–6 агентов по тегам, а не “по именам”.

## 2) Мэппинг (18 ключевых ролей → типы агентов в пуле)
| MyWave роль (v1.1) | Теги навыков | Где | Кого заменяет в пуле |
|---|---|---|---|
| Product Strategist | product, business, roadmap | pipeline | product lead / strategist |
| Sprint Prioritizer (PM) | product, delivery, decomposition | pipeline | project manager |
| Research Analyst | research, synthesis | pipeline | researcher |
| Solution Architect | arch, systems, api | pipeline | architect |
| Backend Engineer | dev.backend, python | pipeline | backend dev |
| Frontend Engineer | dev.frontend, js | pipeline | frontend dev |
| DevOps Automator | devops, docker, ci | pipeline | devops |
| Data/Analytics Eng | data, metrics, sheets | pipeline | data eng |
| Prompt Engineer | prompt, llm, guardrails | pipeline | prompt specialist |
| UX/UI Designer | ux, flows, ui | pipeline | ux designer |
| Content Producer | content, editorial | pipeline | editor |
| Brand Guardian | brand, tone, visual | pipeline/roundtable | brand lead |
| Event Producer | event_ops, runbook | pipeline | event manager |
| QA Evidence Collector | qa, testing | roundtable | qa |
| Security Reviewer | security, privacy | roundtable | security |
| Legal Compliance | legal, compliance | roundtable | legal |
| Finance Planner | finance, unit_econ | roundtable | finance |
| Reality Checker | feasibility, truth-test | roundtable/court | red team / critic |

## 3) Правила несовместимости (anti-self-review)
- Агент-автор не может быть ревьюером того же артефакта.
- Architect не может выполнять Security review своих решений.
- Content author не может быть Brand reviewer спорных кейсов.

## 4) Как подключить реальный список 51 агента
Сделай файл `config/agents_pool.yaml`:
- id, name, tags[], stage_allowed[], notes.
AGM будет выбирать по tags.

## 5) Минимальный формат агента в пуле (YAML)
```yaml
id: "agent_17"
name: "Backend Specialist #2"
tags: ["dev.backend","python","product_dev"]
stage_allowed: ["PIPELINE"]
deny_pairs: ["agent_qa_01"]   # опционально
```
