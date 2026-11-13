# Cross-layer effectiveness audit

Синтез — read-only; audit только при **явном запросе** synthesis (опционально, для аналитики).

| event_type | Когда |
|------------|-------|
| `cross_layer_effectiveness_synthesized` | После успешного вызова `synthesize_cross_layer_summary` (если включено) |
| `cross_layer_alignment_conflict_detected` | При обнаружении conflict (collaboration improved + tuning worse) |

Payload: `window_days`, `alignment_count`, `conflict_types[]`.

Не обязательны для MVP; можно добавить позже при необходимости.
