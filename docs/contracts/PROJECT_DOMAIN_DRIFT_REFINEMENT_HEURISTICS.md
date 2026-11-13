# Project-domain Drift Refinement Heuristics (Phase 11.9)

## Healthy vs harmful drift

**Drift** = dominant domain сменился между previous и current подокном.

### Healthy drift (transitional, не intervention)

- task_count_previous ≥ 2 и task_count_current ≥ 2
- Нет override_heavy
- Смена домена между родственными или ожидаемыми (например legal → finance при смене фокуса проекта)
- **Порог**: если task_count_previous + task_count_current < 8 → считать transitional (мало данных для «вредности»)

### Harmful drift (attention_needed, intervention)

- task_count_previous ≥ 4 и task_count_current ≥ 4 (достаточно данных)
- override_count / task_count > 0.15 (много коррекций) — усиливает harmful
- Или: drift + domain_instability_signal — нестабильность усугубляет

### Explicit thresholds

| условие | classification |
|---------|----------------|
| drift + total_tasks < 8 | transitional |
| drift + override_rate > 0.15 | attention_needed (harmful) |
| drift + instability_signal | attention_needed (harmful) |
| drift + total_tasks ≥ 8, override_rate ≤ 0.15, no instability | transitional (monitor) |
| drift + total_tasks ≥ 12, override_rate > 0.1 | attention_needed |

## Weak signal vs real attention

- weak_signal (lifecycle) → refinement_class = weak_signal, intervention_needed = false
- drifting с малым объёмом → transitional
- drifting с достаточным объёмом + override/instability → attention_needed
