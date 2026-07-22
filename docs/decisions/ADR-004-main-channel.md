# ADR-004: Main MVP Channel

- Статус: Accepted (draft baseline)
- Дата: 2026-04-07

## Контекст

Система должна запускаться и масштабироваться вокруг одного главного канала MVP, без распыления на равноправные UX-контуры.

## Решение

- Главный канал MVP: `Telegram-first` (command + notify + approve).
- Главный исполнитель: `Cursor executor`.
- Dashboard/Web/Desktop: вторичные поверхности мониторинга и управления.

## Обоснование

- Telegram уже является рабочим каналом owner interaction.
- Cursor покрывает основную execution-практику для code/content/docs задач.
- Такой контур снижает время интеграции и миграционные риски.

## Политика approve для critical actions

Approve обязателен минимум для:

- запись в кодовую базу;
- git commit/push/patch;
- deploy/release/prod changes;
- file write вне sandbox/tmp;
- внешние API actions;
- сообщения от system Telegram bot в боевые каналы;
- операции с персональными данными;
- денежные/юридические/публичные действия;
- destructive ops.

Read-only действия approve не требуют.

## Последствия

- Любой новый канал обязан сохранять policy parity с Telegram path.
- Нельзя строить desktop-first архитектуру до закрытия MVP-задолженности.
