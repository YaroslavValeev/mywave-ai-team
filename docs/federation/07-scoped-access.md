# S1b.1: scoped repository и отдельные права проекта

Это внутренний компонент, не завершённая изоляция существующего приложения.
Зависит от S1a / PR №80. Migration 009 добавляет ProjectAccessGrant с role,
expiry/revocation и уникальной парой project/principal. Никаких автоматических
grants, membership seeds или новых HTTP endpoints нет.

## Реализовано

`app/workspaces/access.py` предоставляет Scope и ScopedRepository. Для любого
чтения/записи требуются одновременно действующие workspace membership и
отдельный project grant с подходящей ролью. Владелец workspace не получает
права на проекты по совпадению имени; JOINT не объединяет соседние базы.

Task lookup и списки задач/памяти ограничиваются workspace_id И project_id
в SQL до limit. Legacy null и mismatched records не выдаются. Возвращаются
неизменяемые DTO, без lazy ORM relationships. Создание задачи берёт workspace
из Scope, не из текста, и добавляет audit в одной caller-owned транзакции.
Ошибки отказа не раскрывают существование чужого объекта или его содержимое.

Grant/membership заново читаются с populate_existing при каждом обращении:
identity map не должен сохранять отозванное разрешение. Для записи PostgreSQL
FOR UPDATE удерживает workspace/project/grant rows до завершения транзакции,
сериализуя конкурирующий permission update. Это может ограничить throughput;
при нынешней single-owner нагрузке приоритет — корректность. Для чтения caller
должен использовать короткие READ COMMITTED transactions; долговечный snapshot
с repeatable-read не подходит для немедленной ревокации.

Cache key включает principal/workspace/project/policy version и revision
данных. Перед каждым cache lookup требуется новый вызов authorization; сам
ключ не является capability и не даёт права получать старые данные.
Общий cache/индекс здесь не создаётся.

## Что ещё обязательно до включения

- Principal поступает из аутентифицированного server context. Переданный
  вызывающим кодом Scope не является доказательством личности, LLM не может
  назначать actor. Текущий единый owner API key не заменяет эту интеграцию.
- Старые API/UI/list/export/search/artifacts/background handlers должны
  перейти на scoped operations или явно отклонять scoped records.
- Execution packs, очереди и file/source retrieval должны проверять scope,
  отозванные права и исходный контекст при каждом выполнении.
- Источники с restricted/sensitive данными требуют отдельной классификации,
  основания/мандата; этот repository не выдаёт такие права.
- Denied events требуют отдельного audit sink с учётом rollback вызывающей
  транзакции. Здесь реализован audit успешного scoped task create.

Поэтому Federation intake, новый агент руководителя и production backfill
по-прежнему выключены. Наличие двух таблиц grants не означает готовую систему
разграничения всех каналов. S1b.2 должен закрыть перечисленные точки входа.

## Проверки и откат

Локальный PowerShell, каталог
`F:\Проекты MyWave\NEW2026\AI-Team\.codex-tmp\federation-scoped-access`:

```powershell
Set-Location -LiteralPath 'F:\Проекты MyWave\NEW2026\AI-Team\.codex-tmp\federation-scoped-access'
python -m pytest tests/isolated --confcutdir=tests/isolated -q -p no:cacheprovider
```

Проверяются три вида workspace, отдельность Media/Sponsor, read/write роли,
expiry/revocation, внешний revoke загруженного grant, чужие id/null records,
partition cache, injection текста, atomic audit rollback и constraints 009.
008 full-chain test привязан явно к 008, а актуальный head проверяется
отдельным restore rehearsal. Для PostgreSQL используется только disposable
WORKSPACE_TEST_DATABASE_URL с префиксом базы ai_team_workspace_qa_.

Проверено 19.10.2026: локально 42 passed / 1 PG-only skipped. В изолированном
server Docker SQLite+PostgreSQL 81 passed / 1 SQLite-chain skipped; четыре
Scope validation cases не зависят от DB и выполняются один раз. Regression
377 passed / 1 Cursor CLI skipped. Custom pg_dump схемы 009 восстановлен в
отдельную QA-БД, все rows 17 таблиц совпали, включая project grants.
Dump SHA256: `8c164015ce5db8c64820d1777242768fc3f7313256171c089dae9cece2a45590`.
Evidence:
`/opt/mywave/ai-team-runtime/workspace-qa-20261019/ai-team-workspace-qa-7b58db2fd9ea471abcce855e615fed33/qualification.json`.
Source overlay hashes сохранены, production_changed=false, cleanup=passed.
Это source/dependency qualification, не построенный deployable image.

Откат приложения сохраняет additive schema и grants. Downgrade 009 разрешён
только при пустой таблице grants и не удаляет другие записи. Попытка убрать
существующие права через downgrade отклоняется; нужен отдельный recovery plan.
Новый release helper с поддержкой 009 и Owner-approved выпуск потребуются
позже. Код текущего production и его migration 007 этим PR не меняются.
