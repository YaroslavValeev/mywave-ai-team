# Project–domain heuristics (Phase 10.3)

Explainable rule-based правила для project–domain mapping. Без opaque score.

## Dominant domain

- **Правило:** dominant_domain = домен экспертизы (effective primary_domain), у которого максимальное число задач среди активных и недавних задач проекта.
- **Учёт:** только задачи в статусах active (не DONE/ARCHIVED); при равенстве — первый по алфавиту или с большей долей пересчитанной по всем задачам проекта.
- **Источник:** get_effective_domain_context(task_id, task.owner_text) для каждой задачи проекта.

## Secondary domains

- **Правило:** secondary_domains = домены с числом задач ≥ 2 и долей ≥ 15% от учтённых задач (или один следующий после dominant по счёту).
- **Порог:** минимум 2 задачи в домене, иначе secondary не выводим.

## Mismatch signals

- **override_heavy:** в проекте ≥ 2 задач с активным domain override → сигнал «много ручных правок домена».
- **correction_rate:** доля задач с override среди активных > 30% → «высокий процент ручной коррекции домена».
- **dominant_vs_project_key:** project_key (сейчас = task.domain/task_type) может не совпадать с dominant_domain (expertise); если dominant_domain другой и явно доминирует — можно сигнализировать «фактическая экспертиза проекта — X» (informational).

## Weak mapping

- **Правило:** mapping_confidence = «low», если учтённых задач < 3 или максимальная доля одного домена < 40%.
- **«medium»:** 3–9 задач или доля 40–60%.
- **«high»:** ≥ 10 задач и доля dominant ≥ 60%.

## Обновление

- updated_at = момент вызова (on read); отдельного хранилища нет, всё считается от текущих задач и effective domain context.
