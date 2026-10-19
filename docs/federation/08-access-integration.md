# S1b.2: интеграция границ доступа

Текущий контракт интеграции. Уточняет ограничения этапов S1a/S1b.1, описанные
в 06/07. Не вводит официальных мандатов и не включает профильных агентов.
Production rollout и включение intake являются отдельными Owner Gates.

## Матрица реально подключённых путей

| Путь | Реализация |
|---|---|
| Существующие API/UI/Telegram | get_session_factory создаёт LegacySession; ORM SELECT/relationship loaders исключают scoped проекты, задачи, память и связанные events/decisions/runs/handoffs |
| Запись через старые handlers | before_flush проверяет workspace и родительские project/task; запрещены bulk insert/mappings/raw SQL и переназначение scope через bulk update |
| Runtime/stop и aliases missions | HTTP guard проверяет authenticated owner/signed task link и запрещает scoped id до чтения in-memory runtime или постановки работы в очередь |
| Background/retention/global memory retrieval | та же LegacySession без request context: scoped records не видны даже в новом потоке; retention не удаляет их как legacy |
| Legacy business cache | каждый lookup заново получает visible task ids; классификация исключает прежний payload из cache hit |
| Документы/UI/download/API/Telegram/pipeline attachments/patch approval | общий legacy_path запрещает зарезервированный workspace namespace и файлы classified task, включая старые flat paths, symlink и hardlink aliases |
| Новый API и HTML overview | отдельный scoped router; trusted server principal, membership И project grant, SQL predicates до limit, DTO и no-store |
| Scoped files | повторная авторизация; Handoff привязан к разрешённому task, classification=internal и usage_rights=owner_authorized; только собственный namespace, без symlinks и внешних путей, максимум 5 MiB |
| Scoped execution/orchestration/Execution Pack | явный отказ до side effects: подходящие scope-bound executor profiles/mandates ещё не зарегистрированы |
| Denied audit | отдельная короткая транзакция с principal/scope ids без токенов, содержимого и файловых путей; rollback рабочей транзакции не стирает отказ |

LegacySession — граница прикладного кода, не PostgreSQL RLS и не защита от
оператора с прямым SQL/root доступом. Административные миграции/backfill требуют
отдельной стандартной Session, проверенного mapping и maintenance window.
В приложении прямые engine connections используются только для DB health и
migration identity; они не предоставляются HTTP/LLM как произвольный SQL tool.
Новые feature handlers должны использовать ScopedRepository, а не стандартную
Session для пользовательских запросов. Обход filters через execution options
не предусмотрен. Shared owner memory остаётся owner-only, не служит импортом
данных Федерации; scoped orchestration не запускается через legacy pipeline.

Дополнительно запрещены from_statement/textual SQL и произвольные literal SQL
фрагменты внутри ORM statement: они способны обойти with_loader_criteria.
Этот путь воспроизведён до запрета и закреплён отрицательными тестами; безопасный
COUNT(*) остаётся поддержан. Это не заменяет DB privileges/RLS против прямого
административного подключения вне LegacySession.

## Аутентификация и поддержанные операции

По умолчанию WORKSPACE_ACCESS_ENABLED=false: новые маршруты возвращают 404.
Server-side WORKSPACE_PRINCIPAL_BINDINGS_JSON содержит список объектов с
principal_id и именем secret env переменной key_env, начинающимся с WORKSPACE_KEY_.
Сами ключи находятся только в env/secret manager. Не в JSON body, URL или логе.
Дубликат токена, отсутствующий secret или невалидный binding дают fail-closed 503.

OWNER_API_KEY/cookie не дают scoped доступа сами по себе. Чтобы связать их с
конкретным principal, оператор явно задаёт WORKSPACE_OWNER_PRINCIPAL_ID; grants
в базе всё равно обязательны. Явный неверный X-API-Key не заменяется cookie.
Cookie POST дополнительно требует X-Workspace-Request: 1; cross-origin CORS
не открыт. Поля principal_id/workspace_id/scope в legacy create/update не
игнорируются молча, а отклоняются. Scoped task body принимает только owner_text.

Prefix: `/api/workspaces/{workspace_id}/projects/{project_id}`.

- GET/POST `/tasks`, GET `/tasks/{task_id}` — чтение/создание внутренних задач.
- GET `/memory` — scoped memory, без inconsistent task links и без публикации
  фактов в Knowledge Platform.
- GET `/overview` — простой HTML список разрешённых задач, escaped текст.
- GET `/tasks/{task_id}/artifacts/{artifact_id}` — разрешённый internal файл.
- POST `/tasks/{task_id}/execution/start` — 409 при отсутствии утверждённого
  scoped executor profile. Это не успешное выполнение и не изменение статуса.

Специальные медицинские/детские данные и официальные/финансовые действия не
поддерживаются этой поверхностью. Нужны отдельные data policy/mandate/action
profiles; project membership их не заменяет. Включение обычного scoped API
не означает готовый «Агент руководителя» или полный контур Федерации.

## Validation

Integration suite использует реальные HTTP handlers и отдельные SQL sessions.
SQLite fixture стала временной файловой БД, чтобы запросы TestClient видели
одну БД через разные соединения; shared StaticPool не используется.
Проверяются legacy read/write/runtime bypass, raw/bulk SQL, signed links,
token actor spoofing, grants/revocation, cookie/CSRF, private files/hardlinks,
cache invalidation, неправильные связи memory и отказ запуска scoped executor.
Негативные тесты не используют production токены/бота или live business data.

Локальный PowerShell, каталог
`F:\Проекты MyWave\NEW2026\AI-Team\.codex-tmp\federation-access-integration`:

```powershell
Set-Location -LiteralPath 'F:\Проекты MyWave\NEW2026\AI-Team\.codex-tmp\federation-access-integration'
python -m pytest tests/isolated --confcutdir=tests/isolated -q -p no:cacheprovider
```

Docker/PostgreSQL qualification выполняется изолированно на сервере: internal
network, отдельная база ai_team_workspace_qa_*, tmpfs, синтетические credentials,
без production volumes/портов. Тестируется также прежний regression suite,
реальный head migration 009, pg_dump/pg_restore и равенство всех таблиц.
Deprecation warnings SQLAlchemy JSON operator и тестовых библиотек сохраняются;
dependency image не обновляется в рамках этой интеграции.

## Выпуск и безопасный откат

Нужен новый image/exact source SHA и release helper, поддерживающий 009.
Старый helper с migration=007 не подходит. До включения intake: свежий
restore-tested backup/config/artifacts, проверка фактического Compose profile,
отсутствие активных миссий и проверка auth/grants на синтетических canaries.
Не классифицировать generic default проект автоматически: legacy intake должен
сохранять отдельный unclassified контекст до согласованного mapping.

Критичное уточнение rollback: после появления реальных scoped данных возврат
на старое приложение БЕЗ LegacySession опасен — оно игнорирует workspace_id.
Отключение WORKSPACE_ACCESS_ENABLED скрывает новый API, но безопасные legacy
guards должны остаться. Для отката нужна версия, сохраняющая границы, либо
maintenance mode с закрытием всех каналов до восстановления/forward fix.
Автоматический возврат к 20476d9 допустим только до classified intake и при
проверенном отсутствии приватных scoped данных. Additive schema сохраняется;
populated workspace/grants не удаляются downgrade автоматически.

Следующий продуктовый этап — registry/decision-history/action gates (S1c),
затем read-only executive briefing. Внешние executor profiles — отдельная
прикладная задача с approval на конкретные inputs и обязательной проверкой
revocation при dequeue. Наличие integration guard не разрешает auto-send,
merge/deploy или действие от имени Федерации.
