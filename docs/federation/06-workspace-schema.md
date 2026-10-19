# S1a: явная классификация рабочих пространств

Статус: schema/backfill implementation; runtime access isolation ещё не включена.
Migration 008 следует за 007. Нового API, бота, agent handler или Compose нет.

## Что меняется

- Workspace: уникальный slug, kind FEDERATION/MYWAVE/JOINT, owner, policy version.
- WorkspaceMembership: principal/role, expiry/revocation; уникальная пара
  workspace/principal. Это не product grant или sensitive-data mandate.
- Nullable workspace_id/FK/index у Project, Task, MemoryEntry. Удаление
  используемого workspace запрещается FK RESTRICT.
- Миграция не создаёт ни workspace, ни membership; ни одной старой записи
  не присваивается MYWAVE или другой контур по названию/ключевым словам.

`app/storage/workspace_backfill.py:classify_project` принимает один явно
проверенный project/workspace mapping, reviewer и source_ref. По умолчанию
возвращает preview без изменений. apply=True только выставляет отсутствующий
workspace у проекта и связанных tasks/memory и пишет AuditEvent в той же
транзакции. Caller управляет commit/rollback; ошибка flush требует rollback.
Повтор не создаёт дубль аудита. Утилита не выдаёт membership и не подтверждает
официальные полномочия. Непривязанные legacy tasks остаются unclassified.

Блокируются конфликт существующего workspace, активные стадии/Run, неизвестная
активность Run, несогласованные связи memory↔task↔project, неизвестный target,
пустой reviewer/source и незавершённые изменения session до вызова. Вызов
делается из чистой транзакции, с ids, полученными до любых посторонних правок.
Посторонние уже flushed изменения caller обязан исключить самостоятельно.

## Граница готовности

Это foundation, не механизм разграничения доступа. Существующие API, search,
artifacts и background writers ещё не используют workspace predicates.
Поэтому добавлять реальные данные Федерации или выполнять production backfill
до S1b запрещено. В PR нет команды массового backfill, автозапуска или seed.
Workspace.owner_id сам по себе не создаёт membership или права пользователя.
Подписанное источником соответствие проект/контур проверяется владельцем;
передача actor/source_ref не является аутентификацией вызвавшего кода.

Сначала применяются mandatory read/write/retrieval/file/cache/run guards,
затем включается intake нового контура. На этапе классификации нужны
остановленные прикладные writers/maintenance window: legacy code ещё не
соблюдает locks проекта как общий протокол. Проверка idle в функции не заменяет
такое окно и не обещает защиту от параллельной записи старого приложения.

## Проверка

Локальный PowerShell, каталог
`F:\Проекты MyWave\NEW2026\AI-Team\.codex-tmp\federation-workspace-schema`:

```powershell
Set-Location -LiteralPath 'F:\Проекты MyWave\NEW2026\AI-Team\.codex-tmp\federation-workspace-schema'
python -m pytest tests/isolated/test_workspace_schema.py --confcutdir=tests/isolated -q -p no:cacheprovider
```

SQLite выполняется всегда. Для отдельного disposable PostgreSQL suite требует
WORKSPACE_TEST_DATABASE_URL с базой `ai_team_workspace_qa_*`; существующая
production DATABASE_URL для этих тестов не используется. Fixture очищает свою
QA-базу. Покрыты constraints, nullable legacy, preview/idempotence, atomic audit
rollback, активность, чужие memory links, upgrade/downgrade и полный PG chain.
PG-only full-chain тест ожидаемо пропускается для SQLite.

Проверено 19.10.2026: локально 20 passed / 1 PG-only skipped; на сервере в
изолированной internal network SQLite+PostgreSQL 41 passed / 1 SQLite-chain
skipped, legacy regression 377 passed / 1 Cursor CLI skipped. Восстановлен
custom-format pg_dump схемы 008 в отдельную QA-БД; все rows 16 таблиц сравнены
с исходной QA-БД, включая memberships, scoped records и audit. Dump SHA256
`3c7260d057f112db0c14d783339eccedf0b4cf8a8327d8ebf44f5e724e6fd765`.
Evidence на сервере:
`/opt/mywave/ai-team-runtime/workspace-qa-20261019/ai-team-workspace-qa-aa615fb6f4484b29a2c86f88c682e29b/qualification.json`.
Использован immutable production dependency image, source overlay с byte hashes
сохранён в evidence; нового release image этот тест не создаёт. Cleanup passed.
Локальный Docker Desktop не запустился; Docker проверки выполнены на сервере,
без production volumes, без host ports и без production credentials. Первый
regression harness запуск имел read-only artifacts path; после исправления
ARTIFACTS_DIR на tmpfs повторный полный прогон прошёл без изменений app logic.

Перед deploy обязательны новый app image/exact SHA, полная regression проверка,
backup и restore на копии, проверка migration 008 и read/write совместимости
старого app. Старый release helper, ожидающий migration 007, для этого PR
не подходит. Требуется отдельный Owner-approved release, PR сам не развёртывает
схему. Production migration version пока не меняется этим PR.

## Rollback

Обычный rollback приложения сохраняет additive schema 008 и классификацию.
Только пока отсутствуют classified данные, старый app может игнорировать новые
nullable поля. После intake требуется rollback с сохранением access guards,
см. текущий контракт 08-access-integration.md. Downgrade разрешён только на пустом
workspace контуре: он сохраняет старые rows и удаляет новые поля/таблицы.
Если есть workspace или classified records, downgrade останавливается до
любого изменения. Нужен отдельный план сохранения/восстановления данных;
автоматически стирать классификацию нельзя.
