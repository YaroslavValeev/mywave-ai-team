# Project-domain lifecycle heuristics (Phase 10.8)

Explainable правила для определения lifecycle_state и сигналов. Никаких opaque score.

## Разбиение окна

- Окно `window_days` (например 30) делится на две половины: **previous** = задачи с created_at в [window_days .. window_days/2] дней назад, **current** = задачи с created_at в последние window_days/2 дней.
- По каждой половине считается распределение доменов через effective_domain_context по задачам.

## Правила

### weak_signal
- В окне меньше **MIN_TASKS** (например 3) задач по проекту, или в обеих половинах суммарно мало задач.
- **Объяснение:** «Мало задач в окне — профиль домена не определён.»

### override_heavy
- В текущем project_domain_profile уже есть mismatch_signal типа `override_heavy` или `correction_rate` (много ручных override).
- **Объяснение:** «Высокая доля ручной коррекции домена по проекту.»

### drifting
- В previous и current подокнах достаточно задач (например ≥ 2 в каждой половине), и **current_dominant_domain ≠ previous_dominant_domain** (или previous был один, current другой).
- **Объяснение:** «Доминирующий домен сменился за период (previous → current).»

### stable_single_domain
- Один и тот же домен доминирует в обеих половинах, его доля в current ≥ **DOMINANT_MIN_SHARE** (например 0.6), вторичных доменов нет или один с малой долей.
- **Объяснение:** «Один домен стабильно доминирует в окне.»

### stable_multi_domain
- В обеих половинах два домена имеют долю ≥ **SECONDARY_MIN_SHARE** (например 0.15), без смены «кто первый».
- **Объяснение:** «Два домена устойчиво значимы в проекте.»

### unstable
- Доля override или fallback высокая, и/или confidence в профиле low, и при этом не подходит под override_heavy отдельно — много «шума» в выборе домена.
- **Объяснение:** «Нестабильный доменный профиль: частые коррекции или fallback.»

## Пороги (примерные)

- MIN_TASKS = 3
- DOMINANT_MIN_SHARE = 0.55
- SECONDARY_MIN_SHARE = 0.15
- Override-heavy: уже задаётся в project_domain_mapping (OVERRIDE_HEAVY_THRESHOLD, CORRECTION_RATE_THRESHOLD).

## Приоритет применения

1. weak_signal (если мало данных).
2. override_heavy (если есть в mismatch_signals).
3. drifting (если сменился dominant).
4. unstable (если низкая уверенность и много override/fallback).
5. stable_multi_domain (если два домена устойчивы).
6. stable_single_domain (по умолчанию при одном доминанте).
