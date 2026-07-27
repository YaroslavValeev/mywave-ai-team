# EXECUTE after Owner approve — checklist (MEDIA outreach)

Статус: draft operational  
Дата: 2026-07-27  
Связано: task #30/#32, OPEN_BACKLOG PN/EX

## Когда

Только после Telegram **✅ Утвердить** на content_pipeline с publish gate.

## Шаги (человек + Cursor; Molt пока не шлёт почту сам)

1. Взять CSV уникальных email: `parsernews_unique_emails_YYYYMMDD.csv` (Owner PC Downloads).  
2. Скопировать на RU (опционально):  
   `app/artifacts/tasks/task_N/execution/contacts_unique.csv`  
3. Проверить согласие / сегмент (не слать всем подряд).  
4. Текст = deliverable из court (`Привет! Это команда MyWave…`).  
5. Рассылка — **вручную** или через согласованный tool; не через боевой TG-бот AI-TEAM без отдельного policy GO.  
6. Записать в artifact `execution/send_log.md`: дата, число получателей, канал, результат.

## Запрещено без отдельного Owner GO

- Массовая отправка из контейнера AI-TEAM  
- Публикация CSV с PII в git / публичный artifact viewer без redaction  

## Rollback

Удалить CSV с RU; не трогать Sheets.
