# Playbook: intervention planning

## Как читать intervention plan

- **do_now** — что сделать в первую очередь.
- **do_next** — что после этого.
- **defer** — что можно отложить.
- **preferred_sequence** — полный порядок при необходимости.

## Как выбирать preferred vs fallback

- **Preferred** — путь с safe action или наименьшим ручным шагом.
- **Fallback** — если preferred недоступен (например, execution уже закрыт) — следующий в последовательности.

## Когда intervention можно делать сразу

- Есть safe_action_key и can_execute_action(role, key) == True.
- Collaboration execution в статусе available/triggered — можно trigger.

## Когда сначала смотреть rationale

- Неочевидный порядок (cross-layer conflict).
- Несколько путей — понять why preferred.

## Когда отложить

- low priority + defer в плане.
- Owner перегружен — взять только do_now.
