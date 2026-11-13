# RATIONALE_SURFACES_PLAYBOOK — Phase 11.0

## Назначение

Playbook описывает, где и как rationale появляется в системе. Rationale — это связка: signal → evidence → headline → recommendation → action.

## Short form vs expanded form

| Форма     | Где                        | Что показывается                                           |
|-----------|----------------------------|------------------------------------------------------------|
| Short     | Task card, project, portfolio, collaboration, refinement | headline, 2–5 evidence_items, recommended_action          |
| Expanded  | API /api/explain/*, debug  | Полный rationale: reason, signals_used, confidence_label, related_objects |

Short form — по умолчанию в UI. Expanded — только по запросу (API, debug).

## Surfaces

### Task card

- **Short**: блок «Почему система так считает» — domain selection, specialization, override status.
- **Evidence**: триаж домена, fallback если был, override reason если есть.

### Project detail

- **Short**: dominant domain, drift/diversification, collaboration hotspot.
- **Evidence**: lifecycle snapshot, hotspot reason, mismatch если есть.

### Portfolio block

- **Short**: почему project в focus list, почему drifting/unstable/override-heavy.
- **Evidence**: top attention reasons, lifecycle summary.

### Collaboration block

- **Short**: почему handoff рекомендуется, bottleneck signals, следующая роль.
- **Evidence**: pending count, hotspot type, recommended action.

### Refinement proposal

- **Short**: почему появился proposal, какие сигналы привели, recommended change, risk/severity.
- **Evidence**: backlog item, fallback/override counts.

### Debug API

- **Expanded**: полный rationale в unified format (см. RATIONALE_MODEL.md).

## Как читать rationale cards

1. **headline** — главный ответ на «почему».
2. **evidence_items** — факты (не более 5, обычно 2–3).
3. **recommended_action** — следующий шаг, если уместно.
4. **confidence_label** — high/medium/low (в expanded).

Если headline непонятен — смотреть evidence_items. Если evidence_items недостаточно — использовать API или deeper analysis.

## Связь с recommendations

Recommendation items (get_next_actions, get_decision_queue) могут включать:
- **rationale_headline** — краткое объяснение.
- **evidence_summary** — список фактов.

Эти поля позволяют показывать rationale прямо в блоке рекомендаций без отдельного вызова explanation API.

## Telegram commands

- `/explain_task <id>` — rationale по задаче.
- `/explain_project <key>` — rationale по проекту.
- `/explain_portfolio` — почему focus list.
- `/explain_refinement [proposal_id]` — rationale refinement.
- `/explain_collaboration [project_key]` — rationale collaboration.

Все команды возвращают short form (компактный текст для Telegram).
