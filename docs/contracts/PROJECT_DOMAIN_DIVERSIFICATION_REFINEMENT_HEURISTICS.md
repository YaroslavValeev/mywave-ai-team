# Project-domain Diversification Refinement Heuristics (Phase 11.9)

## Healthy diversification vs unstable domain mix

### Healthy (stable_multi_domain, normal_evolution)

- Два домена с долей ≥ SECONDARY_MIN_SHARE (0.15)
- Первый домен < 0.75 (нет чёткого доминанта, но два устойчивых)
- Без drift, без instability, без override_heavy
- **Вывод**: «Два домена устойчиво значимы» — нормальная эволюция

### Unstable domain mix (attention_needed)

- Три и более домена с долей > 0.1 каждый — слишком размытый профиль
- Или: stable_multi_domain + domain_instability_signal
- Или: diversification + override_rate > 0.2

### Explicit thresholds

| условие | classification |
|---------|----------------|
| stable_multi_domain, 2 домена, no instability | normal_evolution |
| 3+ доменов с share > 0.1 | attention_needed (unstable mix) |
| stable_multi_domain + instability_signal | attention_needed |
| stable_multi_domain + override_rate > 0.2 | attention_needed |

## Distinction

- **weak_signal**: мало данных, не считать diversification
- **transitional**: drift с малым объёмом
- **normal_evolution**: healthy diversification
- **attention_needed**: harmful drift, unstable mix, override_heavy, unstable
