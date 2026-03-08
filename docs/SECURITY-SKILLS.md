# Security — политика Skills

Политика управления skills в MyWave AI-TEAM. Основание: риски supply-chain и credentials в экосистеме skills (ClawHub, маркетплейсы).

## Правила

1. **Allowlist only** — используем только skills из нашего репо или явно разрешённого каталога.
2. **Запрещён pull из публичных хабов** — никаких marketplace, clawhub, public registry.
3. **Новый skill = PR + code review** — любой skill проходит ревью перед добавлением.
4. **Минимальные секреты** — skills не получают сырые ключи, только capabilities через gateway.

## Конфиг

`app/config/skills_allowlist.yaml`:

- `policy.default: deny`
- `allowlist`: пути `app/`, `skills/`
- `deny`: `*.clawhub.*`, `marketplace`, `public_registry`

## Процесс добавления skill

1. Создать skill в `app/` или `skills/`.
2. Открыть PR.
3. Code review (минимум 1 approve).
4. Merge → skill становится доступен.

## Риски (из публичных обсуждений)

- Вредоносные skills (перехват credentials).
- Supply-chain атаки через зависимости.
- Overprivileged доступ к ключам.

## Меры

- Allowlist.
- Gateway для секретов.
- Ротация ключей (где возможно).
- Аудит доступа (логирование).
