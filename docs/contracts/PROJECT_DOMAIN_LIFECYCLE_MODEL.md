# Project-domain lifecycle model (Phase 10.8)

## Поля

- **project_key** — идентификатор проекта (совпадает с текущим project_key из project_queries).
- **current_dominant_domain** — доминирующий домен в текущем подокне (вторая половина окна).
- **previous_dominant_domain** — доминирующий домен в предыдущем подокне (первая половина окна).
- **dominant_domain_stability** — `stable` | `changed` | `unknown` (changed если current ≠ previous при достаточных данных).
- **domain_drift_signal** — булев или структура: true когда dominant сменился между подокнами.
- **domain_diversification_signal** — true когда два и более домена устойчиво значимы (stable_multi_domain).
- **domain_instability_signal** — true при высокой доле override/fallback и низкой уверенности.
- **domain_mix** — распределение доменов в текущем подокне (domain → count).
- **lifecycle_state** — одно из: `stable_single_domain`, `stable_multi_domain`, `drifting`, `override_heavy`, `unstable`, `weak_signal`.
- **window_days** — размер окна в днях (например 30).
- **updated_at** — время вычисления (ISO).
- **reason** / **explanation** — краткое объяснение для owner (почему такой lifecycle_state).

## Примеры lifecycle_state

- **stable_single_domain** — один домен стабильно доминирует в обоих подокнах.
- **stable_multi_domain** — два домена устойчиво значимы в обоих подокнах, без резкой смены.
- **drifting** — dominant domain сменился или заметно ослаб между подокнами.
- **override_heavy** — высокая доля override в проекте (уже есть в mismatch_signals).
- **unstable** — частые correction/fallback, domain mix сильно меняется или низкая уверенность.
- **weak_signal** — мало задач в окне, нельзя уверенно определить профиль.
