# Rationale Heuristics (Phase 11.0)

## Назначение

Rule-based правила для построения readable explanation из существующих signals.

## Headline

- Максимум 1–2 предложения.
- Формат: «[Субъект]: [Основной вывод]. [Причина кратко].»
- Примеры:
  - «Домен: legal — по ключевым словам в задаче.»
  - «Проект general: доминанта stable, drift нет.»
  - «Collaboration: handoff executor→owner — pending approvals.»

## Evidence items

- Максимум 5, обычно 2–3.
- Каждый — одно короткое утверждение.
- Источники: domain_triage, override_store, specialization, lifecycle, collaboration, refinement_backlog.

## Confidence label

- **high** — есть явные сигналы, override нет или подтверждён.
- **medium** — сигналы частичные, fallback использован.
- **low** — слабый сигнал, мало данных, weak_signal lifecycle.

## Recommended action

- Берётся из источника (recommended_action, suggested_action).
- Если несколько — приоритет: owner-facing > collaboration > refinement.
- Не более 1 предложения.

## Запрещено

- Свободная генерация текста без привязки к signals.
- Длинные дампы (raw JSON, внутренние структуры).
- Opaque scoring или «уверенность 0.87».
