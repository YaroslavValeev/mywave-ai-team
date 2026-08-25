# MyWave AI-TEAM v1: readiness и эксплуатация

Дата локальной проверки: **2026-08-25**.

## Статус

Локальный v1-кандидат работает в Docker и прошёл unit/integration, browser и изолированный Docker E2E. Это не является доказательством состояния production: production-деплой и внешние бизнес-действия в рамках этой работы не выполнялись.

## Что владелец может делать

1. Войти в `/office` один раз по owner-паролю; подписанная cookie-сессия авторизует Office API без ключа в URL.
2. Создать миссию, добавить `.md`, `.txt` или `.docx`, запустить/остановить AI-Team и видеть текущую фазу, исполнителя, прогресс и live-события.
3. Общаться с командой на русском, открыть или скачать handoff/report/verdict и выбрать approve, rework, clarify или merge в допустимой фазе.

## Локальный запуск с установленной Ollama

Из корня проекта в PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/local_stack_start.ps1 -FullAI -NoCaddy
```

С принудительной пересборкой:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/local_stack_start.ps1 -FullAI -NoCaddy -Build
```

Скрипт использует `qwen2.5:3b`, отключает локальный Telegram polling и stage-notify, ждёт Docker health до 120 секунд и публикует Office на `http://localhost:8080/office`.

## Быстрая проверка

```powershell
docker compose ps
Invoke-RestMethod http://localhost:8080/health | ConvertTo-Json -Depth 5
docker compose logs --tail 100 app
```

PASS:

- `app` и `postgres` имеют статус `healthy`;
- `/health` возвращает `status=ok` и непустой `release.commit_sha`;
- в app-логах есть `Telegram polling disabled`, нет нового `TelegramConflictError`;
- `/office` после входа загружает данные без `Unauthorized`.

## Доказанный E2E

Изолированный Docker-прогон с отдельной SQLite проверил три сценария:

| Проект | Маршрут | Handoffs | Документы | Финал |
|---|---|---:|---:|---|
| SnowPolia | `GAME/economy_balance` | 4 | 6 | `DONE` |
| Sponsorship Platform | `SPONSOR_PLATFORM/mvp_scoring` | 5 | 7 | `DONE` |
| ExtremeMedia | `RND_EXTREME/judge_console_mvp` | 5 | 7 | `DONE` |

Для каждого сценария проверены русский verdict/report, чат команды, `pipeline_done`, `roundtable_done`, `orchestration_done`, owner approve и итоговый `DONE`.

## Production gates

До объявления production ready обязательны отдельные подтверждения на целевом сервере:

1. Чистый commit SHA и успешный CI полного тестового набора.
2. Backup Postgres и проверенный restore-runbook без удаления текущих данных.
3. `docker compose config`, миграции Alembic, health app/postgres/reverse proxy.
4. Проверка реального Telegram intake/callback без конфликта polling.
5. Проверка HTTPS, DNS, firewall и mobile Office через публичный URL.
6. Один канонический production smoke без внешней публикации/денег и явный Owner GO.

Пока эти пункты не подтверждены свежими данными, корректный статус: **local v1 candidate, production unverified**.

## Rollback

1. Зафиксировать текущий image tag и commit SHA до деплоя.
2. Не удалять volumes и не использовать `docker compose down -v`.
3. При регрессии вернуть предыдущий image/commit, выполнить `docker compose up -d` и дождаться health.
4. Если была миграция, использовать её документированный downgrade только после backup; иначе восстановить совместимый image без изменения БД.
5. Проверить `/health`, `/api/system/health`, Office login и Telegram polling.

## Известные границы v1

- `Stop AI-Team` отменяет выполнение на безопасной checkpoint-точке; уже выполняющийся вызов локальной LLM может завершиться до фактической остановки.
- Локальная 3B-модель медленнее rule-based режима; UI остаётся живым благодаря фоновому job и polling.
- Runner/PR и Molt являются опциональными интеграциями и не блокируют локальную работу Office, но требуют отдельной production-проверки, если включены.
